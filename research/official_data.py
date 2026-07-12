"""Fetch and publish public-display-safe official data snapshots.

Every displayed metric keeps its own source and value date. Restricted feeds
are deliberately absent from this module so a public dashboard cannot silently
inherit an internal/test-only observation.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from .calculations import yield_spread
from .credit_official import FederalReserveSLOOSProvider, TreasuryHQMProvider
from .fed_h10 import FederalReserveH10Provider
from .fed_h41 import FederalReserveH41Provider
from .fed_prates import FederalReservePRATESProvider
from .macro_official import BEANIPAProvider, CensusMRTSProvider
from .models import (
    DashboardSnapshot,
    IngestionRun,
    MetricSnapshot,
    Observation,
    RawArtifact,
    Source,
    TreasuryAuction,
)
from .providers import (
    BLSProvider,
    FederalReserveRSSProvider,
    FiscalDataProvider,
    NYFedMarketsProvider,
    TreasuryRatesProvider,
)
from .services import (
    ensure_source,
    public_display_license_q,
    public_source_notices,
    record_provider_result,
    store_fed_documents,
    store_series_observations,
    store_treasury_auctions,
)

BLS_SERIES = (
    "CES0000000001",
    "LNS14000000",
    "CES0500000003",
    "JTS000000000000000JOL",
    "CUSR0000SA0",
    "CUSR0000SA0L1E",
    "WPSFD4",
)

FRESHNESS_DAYS = {
    "intraday": 1,
    "daily": 4,
    "weekly": 10,
    "monthly": 45,
    "quarterly": 120,
    "annual": 400,
}


def _has_publishable_run(runs: Iterable[IngestionRun]) -> bool:
    """Publish only when the whole refresh group is complete and non-empty."""

    completed = list(runs)
    return bool(completed) and all(
        run.status == IngestionRun.Status.SUCCESS and run.row_count > 0
        for run in completed
    )


def _fresh_until(observation: Observation) -> datetime:
    """Return a deadline from the observation period end, not period start."""

    value_date = observation.value_date
    frequency = observation.series.frequency
    if frequency == "monthly":
        day = calendar.monthrange(value_date.year, value_date.month)[1]
        period_end = value_date.replace(day=day)
    elif frequency == "quarterly":
        quarter_end_month = ((value_date.month - 1) // 3 + 1) * 3
        day = calendar.monthrange(value_date.year, quarter_end_month)[1]
        period_end = value_date.replace(month=quarter_end_month, day=day)
    elif frequency == "annual":
        period_end = value_date.replace(month=12, day=31)
    else:
        period_end = value_date
    return period_end + timedelta(days=FRESHNESS_DAYS.get(frequency, 4))


def _real_observations(series_key: str):
    return (
        Observation.objects.filter(series__key=series_key.lower())
        .exclude(source__key="demo-market")
        .filter(public_display_license_q())
        .select_related("series", "source")
        .distinct()
        .order_by("-value_date")
    )


def _metric(
    series_key: str,
    label: str,
    *,
    decimals: int = 2,
    suffix: str = "",
    scale: Decimal = Decimal("1"),
) -> dict[str, Any] | None:
    observations = list(_real_observations(series_key)[:2])
    if not observations:
        return None
    latest = observations[0]
    value = latest.value * scale
    previous = observations[1].value * scale if len(observations) > 1 else None
    change = value - previous if previous is not None else None
    fresh_until = _fresh_until(latest)
    quality_status = latest.quality_status
    if timezone.now() > fresh_until and quality_status == Observation.Quality.FRESH:
        quality_status = Observation.Quality.STALE
    return {
        "key": series_key.lower(),
        "label": label,
        "value": float(value),
        "display_value": f"{value:,.{decimals}f}{suffix}",
        "change": round(float(change), decimals) if change is not None else None,
        "change_unit": suffix,
        "unit": suffix,
        "quality_status": quality_status,
        "source": latest.source.name,
        "source_key": latest.source.key,
        "source_keys": [latest.source.key],
        "as_of": latest.as_of.isoformat(),
        "value_date": latest.value_date.isoformat(),
        "fetched_at": latest.fetched_at.isoformat(),
        "fresh_until": fresh_until.isoformat(),
        "batch_id": str(latest.batch_id),
        "metadata": latest.metadata,
    }


def _derived_metric(
    key: str,
    label: str,
    left_key: str,
    right_key: str,
    *,
    basis_points: bool = False,
) -> dict[str, Any] | None:
    left = _real_observations(left_key).first()
    right = _real_observations(right_key).first()
    if not left or not right:
        return None
    value = Decimal(str(yield_spread(left.value, right.value, basis_points=basis_points)))
    suffix = "bp" if basis_points else "%"
    left_deadline = _fresh_until(left)
    right_deadline = _fresh_until(right)
    fresh_until = min(left_deadline, right_deadline)
    return {
        "key": key,
        "label": label,
        "value": float(value),
        "display_value": f"{value:+,.0f}{suffix}" if basis_points else f"{value:+,.2f}{suffix}",
        "change": None,
        "unit": suffix,
        "quality_status": Observation.Quality.ESTIMATED,
        "source": f"Atlas Macro 计算：{left.source.name} − {right.source.name}",
        "source_key": "internal",
        "source_keys": sorted({left.source.key, right.source.key, "internal"}),
        "as_of": min(left.as_of, right.as_of).isoformat(),
        "value_date": min(left.value_date, right.value_date).isoformat(),
        "fetched_at": max(left.fetched_at, right.fetched_at).isoformat(),
        "fresh_until": fresh_until.isoformat(),
        "batch_id": f"{left.batch_id},{right.batch_id}",
        "metadata": {
            "formula": f"{left_key} - {right_key}",
            "source_keys": sorted({left.source.key, right.source.key}),
        },
    }


def _linear_metric(
    key: str,
    label: str,
    terms: tuple[tuple[Decimal, str], ...],
    *,
    scale: Decimal = Decimal("1"),
    decimals: int = 2,
    suffix: str = "",
) -> dict[str, Any] | None:
    """Calculate a transparent linear combination from latest public inputs."""

    inputs: list[tuple[Decimal, Observation]] = []
    for coefficient, series_key in terms:
        observation = _real_observations(series_key).first()
        if observation is None:
            return None
        inputs.append((coefficient, observation))
    value = sum((coefficient * item.value for coefficient, item in inputs), Decimal("0"))
    scaled_value = value * scale
    deadlines = [_fresh_until(item) for _, item in inputs]
    fresh_until = min(deadlines)
    quality = (
        Observation.Quality.STALE if timezone.now() > fresh_until else Observation.Quality.ESTIMATED
    )
    formula = " ".join(
        ("+ " if coefficient > 0 and index else "- " if coefficient < 0 else "") + series_key
        for index, (coefficient, series_key) in enumerate(terms)
    )
    return {
        "key": key,
        "label": label,
        "value": float(scaled_value),
        "display_value": f"{scaled_value:,.{decimals}f}{suffix}",
        "change": None,
        "unit": suffix,
        "quality_status": quality,
        "source": "Atlas Macro 计算：" + formula,
        "source_key": "internal",
        "source_keys": sorted({item.source.key for _, item in inputs} | {"internal"}),
        "as_of": min(item.as_of for _, item in inputs).isoformat(),
        "value_date": min(item.value_date for _, item in inputs).isoformat(),
        "fetched_at": max(item.fetched_at for _, item in inputs).isoformat(),
        "fresh_until": fresh_until.isoformat(),
        "batch_id": ",".join(str(item.batch_id) for _, item in inputs),
        "metadata": {
            "formula": formula,
            "input_series": [series_key for _, series_key in terms],
            "source_keys": sorted({item.source.key for _, item in inputs}),
        },
    }


def _existing(*metrics: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [metric for metric in metrics if metric is not None]


def _curve_rows(prefix: str, tenors: Iterable[str]) -> list[dict[str, Any]]:
    rows = []
    for tenor in tenors:
        item = _metric(f"{prefix}-{tenor}", tenor, suffix="%")
        if item:
            rows.append(item)
    return rows


def _history_rows(series: dict[str, str], *, limit: int = 120) -> list[dict[str, Any]]:
    """Align public observations by date while preserving semantic series labels."""

    by_date: dict[str, dict[str, Any]] = {}
    for series_key, label in series.items():
        observations = list(_real_observations(series_key)[:limit])
        for observation in reversed(observations):
            day = observation.value_date.date().isoformat()
            row = by_date.setdefault(day, {"date": day, "_source_keys": []})
            row[label] = float(observation.value)
            row["_source_keys"] = sorted(
                {*row["_source_keys"], observation.source.key}
            )
    return [by_date[day] for day in sorted(by_date)]


def _earliest_fresh_until(rows: Iterable[dict[str, Any]]) -> str | None:
    return min(
        (item["fresh_until"] for item in rows if item.get("fresh_until")),
        default=None,
    )


def _sofr_market_metrics() -> list[dict[str, Any]]:
    observations = list(_real_observations("SOFR")[:2])
    if not observations:
        return []
    latest = observations[0]
    previous = observations[1] if len(observations) > 1 else None
    fresh_until = _fresh_until(latest)
    quality = Observation.Quality.STALE if timezone.now() > fresh_until else latest.quality_status
    definitions = (
        ("sofr-volume", "SOFR 成交量", "volumeInBillions", " USD bn", 0),
        ("sofr-p99", "SOFR 99P", "percentPercentile99", "%", 2),
    )
    metrics: list[dict[str, Any]] = []
    for key, label, metadata_key, suffix, decimals in definitions:
        raw_value = latest.metadata.get(metadata_key)
        if raw_value is None:
            continue
        value = Decimal(str(raw_value))
        previous_raw = previous.metadata.get(metadata_key) if previous else None
        change = value - Decimal(str(previous_raw)) if previous_raw is not None else None
        metrics.append(
            {
                "key": key,
                "label": label,
                "value": float(value),
                "display_value": f"{value:,.{decimals}f}{suffix}",
                "change": float(change) if change is not None else None,
                "change_unit": suffix,
                "unit": suffix,
                "quality_status": quality,
                "source": latest.source.name,
                "source_key": latest.source.key,
                "source_keys": [latest.source.key],
                "as_of": latest.as_of.isoformat(),
                "value_date": latest.value_date.isoformat(),
                "fetched_at": latest.fetched_at.isoformat(),
                "fresh_until": fresh_until.isoformat(),
                "batch_id": str(latest.batch_id),
                "metadata": {"upstream_field": metadata_key},
            }
        )
    percentile_99 = latest.metadata.get("percentPercentile99")
    if percentile_99 is not None:
        tail = (Decimal(str(percentile_99)) - latest.value) * Decimal("100")
        metrics.append(
            {
                "key": "sofr-p99-minus-rate",
                "label": "SOFR 99P−SOFR",
                "value": float(tail),
                "display_value": f"{tail:+,.0f}bp",
                "change": None,
                "unit": "bp",
                "quality_status": Observation.Quality.ESTIMATED,
                "source": f"Atlas Macro 计算：{latest.source.name}",
                "source_key": "internal",
                "source_keys": [latest.source.key, "internal"],
                "as_of": latest.as_of.isoformat(),
                "value_date": latest.value_date.isoformat(),
                "fetched_at": latest.fetched_at.isoformat(),
                "fresh_until": fresh_until.isoformat(),
                "batch_id": str(latest.batch_id),
                "metadata": {
                    "formula": "SOFR percentPercentile99 - percentRate",
                    "source_keys": [latest.source.key],
                },
            }
        )
        iorb = _real_observations("IORB").first()
        if iorb is not None:
            iorb_tail = (Decimal(str(percentile_99)) - iorb.value) * Decimal("100")
            iorb_fresh_until = min(fresh_until, _fresh_until(iorb))
            source_keys = sorted({latest.source.key, iorb.source.key, "internal"})
            metrics.append(
                {
                    "key": "sofr-p99-minus-iorb",
                    "label": "SOFR 99P−IORB",
                    "value": float(iorb_tail),
                    "display_value": f"{iorb_tail:+,.0f}bp",
                    "change": None,
                    "unit": "bp",
                    "quality_status": (
                        Observation.Quality.STALE
                        if timezone.now() > iorb_fresh_until
                        else Observation.Quality.ESTIMATED
                    ),
                    "source": (
                        f"Atlas Macro 计算：{latest.source.name} 99P − {iorb.source.name} IORB"
                    ),
                    "source_key": "internal",
                    "source_keys": source_keys,
                    "as_of": min(latest.as_of, iorb.as_of).isoformat(),
                    "value_date": min(latest.value_date, iorb.value_date).isoformat(),
                    "fetched_at": max(latest.fetched_at, iorb.fetched_at).isoformat(),
                    "fresh_until": iorb_fresh_until.isoformat(),
                    "batch_id": f"{latest.batch_id},{iorb.batch_id}",
                    "metadata": {
                        "formula": "SOFR percentPercentile99 - IORB",
                        "source_keys": sorted({latest.source.key, iorb.source.key}),
                    },
                }
            )
    return metrics


def _sofr_market_history(*, limit: int = 120) -> list[dict[str, Any]]:
    rows = []
    for observation in reversed(list(_real_observations("SOFR")[:limit])):
        row: dict[str, Any] = {
            "date": observation.value_date.date().isoformat(),
            "SOFR": float(observation.value),
            "_source_keys": [observation.source.key],
        }
        if observation.metadata.get("percentPercentile99") is not None:
            row["99P"] = float(observation.metadata["percentPercentile99"])
        rows.append(row)
    return rows


def _auction_snapshot_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    today = timezone.localdate()
    upcoming = list(
        TreasuryAuction.objects.filter(auction_date__gte=today)
        .filter(public_display_license_q())
        .distinct()
        .select_related("source")
        .order_by("auction_date")[:20]
    )
    completed = list(
        TreasuryAuction.objects.filter(auction_date__lte=today, bid_to_cover_ratio__isnull=False)
        .filter(public_display_license_q())
        .distinct()
        .select_related("source")
        .order_by("-auction_date")[:20]
    )
    metrics: list[dict[str, Any]] = []
    if upcoming:
        item = upcoming[0]
        fresh_until = item.fetched_at + timedelta(days=2)
        quality_status = (
            Observation.Quality.STALE
            if timezone.now() > fresh_until
            else item.quality_status
        )
        metrics.append(
            {
                "key": "next-auction",
                "label": "下次拍卖",
                "value": 0,
                "display_value": f"{item.auction_date} · {item.security_term}",
                "change": None,
                "quality_status": quality_status,
                "source": item.source.name,
                "source_key": item.source.key,
                "source_keys": [item.source.key],
                "as_of": item.fetched_at.isoformat(),
                "value_date": item.auction_date.isoformat(),
                "fetched_at": item.fetched_at.isoformat(),
                "fresh_until": fresh_until.isoformat(),
                "batch_id": str(item.batch_id),
            }
        )
        if item.offering_amount is not None:
            metrics.append(
                {
                    "key": "next-offering",
                    "label": "下次发行额",
                    "value": float(item.offering_amount / Decimal("1000000000")),
                    "display_value": f"${item.offering_amount / Decimal('1000000000'):,.1f}B",
                    "change": None,
                    "quality_status": quality_status,
                    "source": item.source.name,
                    "source_key": item.source.key,
                    "source_keys": [item.source.key],
                    "as_of": item.fetched_at.isoformat(),
                    "value_date": item.auction_date.isoformat(),
                    "fetched_at": item.fetched_at.isoformat(),
                    "fresh_until": fresh_until.isoformat(),
                    "batch_id": str(item.batch_id),
                }
            )
    if completed:
        item = completed[0]
        fresh_until = item.fetched_at + timedelta(days=2)
        quality_status = (
            Observation.Quality.STALE
            if timezone.now() > fresh_until
            else item.quality_status
        )
        metrics.append(
            {
                "key": "latest-bid-cover",
                "label": "最近 Bid-to-Cover",
                "value": float(item.bid_to_cover_ratio),
                "display_value": f"{item.bid_to_cover_ratio:.2f}x",
                "change": None,
                "quality_status": quality_status,
                "source": item.source.name,
                "source_key": item.source.key,
                "source_keys": [item.source.key],
                "as_of": item.fetched_at.isoformat(),
                "value_date": item.auction_date.isoformat(),
                "fetched_at": item.fetched_at.isoformat(),
                "fresh_until": fresh_until.isoformat(),
                "batch_id": str(item.batch_id),
            }
        )
    rows = [
        {
            "label": f"{item.security_type} · {item.security_term}",
            "display_value": (
                f"${item.offering_amount / Decimal('1000000000'):,.1f}B"
                if item.offering_amount is not None
                else "待公布"
            ),
            "status": (
                f"Bid/Cover {item.bid_to_cover_ratio:.2f}x"
                if item.bid_to_cover_ratio is not None
                else "已公告，结果待发布"
            ),
            "source": item.source.name,
            "source_key": item.source.key,
            "source_keys": [item.source.key],
            "as_of": item.auction_date.isoformat(),
        }
        for item in [*upcoming, *completed]
    ]
    return metrics, rows


def _store_board_archive_observations(result, source, run) -> int:
    """Persist Board DDP rows plus an immutable ZIP download fingerprint."""

    row_count = store_series_observations(result, source, run)
    archive_hash = str(result.metadata.get("archive_sha256") or "")
    archive_size = int(result.metadata.get("archive_size") or 0)
    source_url = str(result.metadata.get("source_url") or "")
    if archive_hash and source_url:
        RawArtifact.objects.create(
            run=run,
            uri=f"{source_url}#sha256={archive_hash}",
            sha256=archive_hash,
            content_type="application/zip",
            size_bytes=archive_size,
        )
    return row_count


def _store_h41_observations(result, source, run) -> int:
    """Backward-compatible H.4.1 persistence entry point used by tests/jobs."""

    return _store_board_archive_observations(result, source, run)


def _store_prates_observations(result, source, run) -> int:
    return _store_board_archive_observations(result, source, run)


def _store_h10_observations(result, source, run) -> int:
    return _store_board_archive_observations(result, source, run)


def _publish_dashboard(
    *,
    key: str,
    title: str,
    summary: str,
    metrics: list[dict[str, Any]],
    chart_data: list[float] | None = None,
    sections: list[dict[str, Any]] | None = None,
    batch_id: uuid.UUID,
) -> DashboardSnapshot | None:
    if not metrics:
        return None
    as_of_values = [datetime.fromisoformat(item["as_of"]) for item in metrics if item.get("as_of")]
    as_of = min(as_of_values) if as_of_values else timezone.now()
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    component_qualities = {item.get("quality_status") for item in metrics}
    if Observation.Quality.ERROR in component_qualities:
        quality = Observation.Quality.ERROR
    elif Observation.Quality.STALE in component_qualities:
        quality = Observation.Quality.STALE
    elif component_qualities == {Observation.Quality.FRESH}:
        quality = Observation.Quality.FRESH
    else:
        quality = Observation.Quality.ESTIMATED
    source = ensure_source("internal")
    component_batches = sorted(
        {
            batch.strip()
            for item in metrics
            for batch in str(item.get("batch_id") or "").split(",")
            if batch.strip()
        }
    )
    def payload_source_keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            keys = {str(value["source_key"])} if value.get("source_key") else set()
            keys.update(str(item) for item in value.get("source_keys", []) if item)
            keys.update(str(item) for item in value.get("_source_keys", []) if item)
            for nested in value.values():
                keys.update(payload_source_keys(nested))
            return keys
        if isinstance(value, list):
            keys: set[str] = set()
            for nested in value:
                keys.update(payload_source_keys(nested))
            return keys
        return set()

    source_keys = sorted(payload_source_keys([metrics, chart_data or [], sections or []]))
    snapshot_data = {
        "demo": False,
        "metrics": metrics,
        "chart_data": chart_data or [],
        "sections": sections or [],
        "component_batches": component_batches,
        "source_keys": source_keys,
        "required_notices": public_source_notices(source_keys),
        "fresh_until": min(
            (item["fresh_until"] for item in metrics if item.get("fresh_until")),
            default=None,
        ),
        "publication_batch_id": str(batch_id),
    }
    fingerprint_payload = {
        "title": title,
        "summary": summary,
        **snapshot_data,
    }

    def without_volatile_lineage(value: Any) -> Any:
        """Keep the content fingerprint stable across an unchanged re-fetch."""

        if isinstance(value, dict):
            return {
                item_key: without_volatile_lineage(item_value)
                for item_key, item_value in value.items()
                if item_key
                not in {
                    "batch_id",
                    "component_batch_id",
                    "component_batches",
                    "fetched_at",
                    "fingerprint",
                    "fresh_until",
                    "publication_batch_id",
                    "required_notices",
                    "as_of",
                }
            }
        if isinstance(value, list):
            return [without_volatile_lineage(item) for item in value]
        return value

    fingerprint = hashlib.sha256(
        json.dumps(
            without_volatile_lineage(fingerprint_payload),
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ).encode()
    ).hexdigest()
    snapshot_data["fingerprint"] = fingerprint
    latest = (
        DashboardSnapshot.objects.filter(key=key, is_published=True)
        .exclude(source__key="demo-market")
        .order_by("-created_at")
        .first()
    )
    if latest and latest.data.get("fingerprint") == fingerprint:
        return None
    for item in metrics:
        item_value = item.get("value")
        if item_value is None:
            continue
        component_source = Source.objects.filter(key=item.get("source_key", "")).first() or source
        value_date = datetime.fromisoformat(item["as_of"]) if item.get("as_of") else as_of
        if value_date.tzinfo is None:
            value_date = value_date.replace(tzinfo=UTC)
        fetched_at = (
            datetime.fromisoformat(item["fetched_at"])
            if item.get("fetched_at")
            else timezone.now()
        )
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        MetricSnapshot.objects.update_or_create(
            key=f"{key}-{item.get('key', item['label']).lower()}",
            batch_id=batch_id,
            defaults={
                "label": item["label"],
                "value": Decimal(str(item_value)),
                "display_value": item.get("display_value", ""),
                "change": (
                    Decimal(str(item["change"])) if item.get("change") is not None else None
                ),
                "unit": item.get("unit", ""),
                "value_date": value_date,
                "as_of": value_date,
                "fetched_at": fetched_at,
                "source": component_source,
                "quality_status": item.get("quality_status", Observation.Quality.FRESH),
                "license_scope": component_source.license_scope[:120],
                "metadata": {
                    "component_batch_id": item.get("batch_id"),
                    "formula": (item.get("metadata") or {}).get("formula"),
                    "public_snapshot": True,
                },
            },
        )
    return DashboardSnapshot.objects.create(
        key=key,
        title=title,
        as_of=as_of,
        batch_id=batch_id,
        quality_status=quality,
        summary=summary,
        data=snapshot_data,
        source=source,
        is_published=True,
    )


def publish_official_dashboards() -> list[DashboardSnapshot]:
    """Atomically publish dashboards backed only by approved official sources."""

    batch_id = uuid.uuid4()
    nominal_curve = _curve_rows(
        "ust", ("1m", "2m", "3m", "4m", "6m", "1y", "2y", "3y", "5y", "7y", "10y", "20y", "30y")
    )
    real_curve = _curve_rows("tips", ("5y", "7y", "10y", "20y", "30y"))
    hqm_curve = _curve_rows("hqm-par", ("2y", "5y", "10y", "30y"))
    sofr_market_metrics = _sofr_market_metrics()
    auction_metrics, auction_rows = _auction_snapshot_data()
    dashboards: list[DashboardSnapshot] = []
    definitions = [
        {
            "key": "liquidity",
            "title": "流动性",
            "summary": "当前只发布已接入的财政现金与回购利率组件；未完成的综合 LPI 不估算。",
            "metrics": _existing(
                _linear_metric(
                    "net-liquidity",
                    "净流动性",
                    (
                        (Decimal("1"), "WALCL"),
                        (Decimal("-1"), "ONRRP"),
                        (Decimal("-1"), "TGA"),
                    ),
                    scale=Decimal("0.000001"),
                    suffix=" USD tn",
                ),
                _metric(
                    "WALCL",
                    "联储总资产",
                    scale=Decimal("0.000001"),
                    suffix=" USD tn",
                ),
                _metric(
                    "WRBWFRBL",
                    "准备金",
                    scale=Decimal("0.000001"),
                    suffix=" USD tn",
                ),
                _metric(
                    "ONRRP", "ON RRP", decimals=3, scale=Decimal("0.001"), suffix=" USD bn"
                ),
                _metric("TGA", "TGA", scale=Decimal("0.001"), suffix=" USD bn"),
                _metric("SOFR", "SOFR", suffix="%"),
                _metric("IORB", "IORB", suffix="%"),
                _derived_metric("sofr-effr", "SOFR−EFFR", "SOFR", "EFFR", basis_points=True),
                _derived_metric("sofr-iorb", "SOFR−IORB", "SOFR", "IORB", basis_points=True),
            ),
            "chart_data": _history_rows({"TGA": "TGA", "ONRRP": "ON RRP"}, limit=90),
        },
        {
            "key": "transmission-chain",
            "title": "美元流动性传导链",
            "summary": "先显示美国财政与 Repo 官方输入；离岸基差、中介能力与资产反应缺口见下方台账，不发布伪精确总分。",
            "metrics": _existing(
                _metric("WRBWFRBL", "准备金", scale=Decimal("0.000001"), suffix=" USD tn"),
                _metric("TGA", "TGA", scale=Decimal("0.001"), suffix=" USD bn"),
                _metric(
                    "ONRRP", "ON RRP", decimals=3, scale=Decimal("0.001"), suffix=" USD bn"
                ),
                _metric("SOFR", "SOFR", suffix="%"),
                _metric("IORB", "IORB", suffix="%"),
                _derived_metric("sofr-effr", "SOFR−EFFR", "SOFR", "EFFR", basis_points=True),
                _derived_metric("sofr-iorb", "SOFR−IORB", "SOFR", "IORB", basis_points=True),
                _metric(
                    "FXSWAP-USD-OUTSTANDING",
                    "央行美元互换",
                    decimals=0,
                    suffix=" USD mn",
                ),
            ),
            "chart_data": _history_rows({"SOFR": "SOFR", "EFFR": "EFFR", "IORB": "IORB"}),
        },
        {
            "key": "fed-balance-sheet",
            "title": "美联储资产负债表",
            "summary": "六个核心序列直接解析 Federal Reserve H.4.1 DDP；周三观察、周四发布，保留每次 ZIP 哈希。",
            "metrics": _existing(
                _metric("WALCL", "总资产", scale=Decimal("0.000001"), suffix=" USD tn"),
                _metric("WSHOTSL", "美债持有", scale=Decimal("0.000001"), suffix=" USD tn"),
                _metric("WSHOMCB", "MBS 持有", scale=Decimal("0.000001"), suffix=" USD tn"),
                _metric("WRBWFRBL", "准备金", scale=Decimal("0.000001"), suffix=" USD tn"),
            ),
            "chart_data": _history_rows(
                {
                    "WALCL": "总资产",
                    "WSHOTSL": "美债",
                    "WSHOMCB": "MBS",
                    "WRBWFRBL": "准备金",
                },
                limit=104,
            ),
        },
        {
            "key": "operations",
            "title": "公开市场操作",
            "summary": "ON RRP 和常备回购按操作日聚合，常备回购合并早午两场；SOMA 为周三国内证券持仓，不等于 H.4.1 总资产。",
            "metrics": _existing(
                _metric(
                    "ONRRP", "ON RRP", decimals=3, scale=Decimal("0.001"), suffix=" USD bn"
                ),
                _metric("SRP", "常备回购", decimals=0, suffix=" USD mn"),
                _metric("SRP-RATE", "常备回购利率", suffix="%"),
                _metric("SOMA-TOTAL", "SOMA", scale=Decimal("0.000001"), suffix=" USD tn"),
            ),
            "chart_data": _history_rows({"SOMA-TOTAL": "SOMA"}, limit=104),
        },
        {
            "key": "fed-funds",
            "title": "联邦基金利率",
            "summary": "SOFR 与 EFFR 直接来自纽约联储，IORB 直接来自 Federal Reserve PRATES；每个卡片单独标记有效日期。",
            "metrics": _existing(
                _metric("EFFR", "EFFR", suffix="%"),
                _metric("SOFR", "SOFR", suffix="%"),
                _metric("IORB", "IORB", suffix="%"),
                _derived_metric("sofr-effr", "SOFR−EFFR", "SOFR", "EFFR", basis_points=True),
                _derived_metric("sofr-iorb", "SOFR−IORB", "SOFR", "IORB", basis_points=True),
            ),
            "chart_data": _history_rows({"SOFR": "SOFR", "EFFR": "EFFR", "IORB": "IORB"}),
        },
        {
            "key": "rates",
            "title": "利率",
            "summary": "政策利率取纽约联储，国债收益率取美国财政部官方日曲线。",
            "metrics": _existing(
                _metric("EFFR", "EFFR", suffix="%"),
                _metric("SOFR", "SOFR", suffix="%"),
                _metric("IORB", "IORB", suffix="%"),
                _metric("UST-2Y", "2Y", suffix="%"),
                _metric("UST-10Y", "10Y", suffix="%"),
                _derived_metric("2s10s", "2s10s", "UST-10Y", "UST-2Y", basis_points=True),
            ),
            "chart_data": _history_rows({"UST-2Y": "2Y", "UST-10Y": "10Y"}),
        },
        {
            "key": "assets-fx",
            "title": "外汇",
            "summary": "日频参考值直接来自 Federal Reserve H.10；广义美元指数不是 ICE DXY，参考汇率也不是可交易实时现货或远期报价。",
            "metrics": _existing(
                _metric("H10-BROAD-DOLLAR", "广义美元指数", decimals=2),
                _metric("H10-EURUSD", "EUR/USD 参考汇率", decimals=4),
                _metric("H10-USDCNY", "USD/CNY 参考汇率", decimals=4),
                _metric("H10-USDJPY", "USD/JPY 参考汇率", decimals=4),
            ),
            "chart_data": _history_rows(
                {
                    "H10-BROAD-DOLLAR": "广义美元指数",
                    "H10-EURUSD": "EUR/USD",
                },
                limit=120,
            ),
        },
        {
            "key": "yield-curve",
            "title": "收益率曲线",
            "summary": "当前名义曲线直接来自美国财政部；利差为 Atlas Macro 透明计算。",
            "metrics": _existing(
                _derived_metric("2s10s", "2s10s", "UST-10Y", "UST-2Y", basis_points=True),
                _derived_metric("3m10s", "3m10s", "UST-10Y", "UST-3M", basis_points=True),
                _derived_metric("5s30s", "5s30s", "UST-30Y", "UST-5Y", basis_points=True),
                _metric("UST-10Y", "10Y", suffix="%"),
            ),
            "chart_data": [
                {"label": item["label"], "yield": item["value"]} for item in nominal_curve
            ],
            "sections": [
                {
                    "title": "财政部名义曲线",
                    "rows": nominal_curve,
                    "fresh_until": _earliest_fresh_until(nominal_curve),
                    "status": (
                        "fresh"
                        if nominal_curve
                        and all(item["quality_status"] == "fresh" for item in nominal_curve)
                        else "stale"
                    ),
                }
            ],
        },
        {
            "key": "real-rates",
            "title": "实际利率",
            "summary": "TIPS 实际利率直接来自美国财政部；盈亏平衡通胀为同期限名义减实际。",
            "metrics": _existing(
                _metric("TIPS-5Y", "5Y 实际利率", suffix="%"),
                _metric("TIPS-10Y", "10Y 实际利率", suffix="%"),
                _derived_metric("5y-bei", "5Y BEI", "UST-5Y", "TIPS-5Y"),
                _derived_metric("10y-bei", "10Y BEI", "UST-10Y", "TIPS-10Y"),
            ),
            "chart_data": [
                {"label": item["label"], "real_yield": item["value"]} for item in real_curve
            ],
            "sections": [
                {
                    "title": "财政部实际利率曲线",
                    "rows": real_curve,
                    "fresh_until": _earliest_fresh_until(real_curve),
                    "status": (
                        "fresh"
                        if real_curve
                        and all(item["quality_status"] == "fresh" for item in real_curve)
                        else "stale"
                    ),
                }
            ],
        },
        {
            "key": "credit",
            "title": "信用市场",
            "summary": "免费版发布 Treasury HQM 高质量企业债收益率与 Fed SLOOS 贷款标准；它们是信用环境代理，不是 ICE OAS 或 CDS。",
            "metrics": _existing(
                _metric("HQM-PAR-10Y", "HQM 10Y", suffix="%"),
                _metric("HQM-PAR-30Y", "HQM 30Y", suffix="%"),
                _metric("SUBLPDMBS_XWB_N.Q", "企业贷款标准", suffix="%"),
                _metric("SUBLPDMBD_XWB_N.Q", "企业贷款需求", suffix="%"),
            ),
            "chart_data": _history_rows(
                {
                    "SUBLPDMBS_XWB_N.Q": "贷款标准",
                    "SUBLPDMBD_XWB_N.Q": "贷款需求",
                },
                limit=24,
            ),
        },
        {
            "key": "credit-spreads",
            "title": "信用利差与收益率代理",
            "summary": "Treasury HQM 是高质量企业债月均 par yield 曲线，不含国债利差、不是 OAS；ICE 分评级 OAS 仍需商业许可。",
            "metrics": _existing(
                _metric("HQM-PAR-2Y", "HQM 2Y", suffix="%"),
                _metric("HQM-PAR-5Y", "HQM 5Y", suffix="%"),
                _metric("HQM-PAR-10Y", "HQM 10Y", suffix="%"),
                _metric("HQM-PAR-30Y", "HQM 30Y", suffix="%"),
            ),
            "chart_data": [
                {"label": item["label"], "HQM par yield": item["value"]}
                for item in hqm_curve
            ],
            "sections": [
                {
                    "title": "Treasury HQM 月均高质量企业债曲线（代理）",
                    "rows": hqm_curve,
                    "fresh_until": _earliest_fresh_until(hqm_curve),
                    "status": "estimated",
                }
            ],
        },
        {
            "key": "credit-stress",
            "title": "信用压力仪表盘",
            "summary": "SLOOS 为季度银行调查：正值贷款标准表示净收紧，需求项按 Board 原始口径展示。尚未将其合成为自有压力总分。",
            "metrics": _existing(
                _metric("SUBLPDMBS_XWB_N.Q", "企业贷款标准", suffix="%"),
                _metric("SUBLPDMBD_XWB_N.Q", "企业贷款需求", suffix="%"),
                _metric("SUBLPDCILS_N.Q", "大中企业 C&I 标准", suffix="%"),
                _metric("SUBLPDCISS_N.Q", "小企业 C&I 标准", suffix="%"),
            ),
            "chart_data": _history_rows(
                {
                    "SUBLPDMBS_XWB_N.Q": "贷款标准",
                    "SUBLPDMBD_XWB_N.Q": "贷款需求",
                },
                limit=24,
            ),
        },
        {
            "key": "rrp-tga",
            "title": "RRP 与 TGA",
            "summary": "TGA 来自 Treasury FiscalData 每日财政报表；ON RRP 来自纽约联储最近有效操作结果，周末不把 latest 空响应当成 0。",
            "metrics": _existing(
                _metric(
                    "ONRRP", "ON RRP", decimals=3, scale=Decimal("0.001"), suffix=" USD bn"
                ),
                _metric("ONRRP-RATE", "ON RRP 利率", suffix="%"),
                _metric("ONRRP-PARTICIPANTS", "交易对手", decimals=0, suffix=" 家"),
                _metric("TGA", "TGA", scale=Decimal("0.001"), suffix=" USD bn"),
            ),
            "chart_data": _history_rows({"TGA": "TGA", "ONRRP": "ON RRP"}, limit=90),
        },
        {
            "key": "reserves",
            "title": "银行准备金",
            "summary": "准备金余额直接来自 Federal Reserve H.4.1；银行资产占比与充裕度阈值在分母及方法完成前保持空缺。",
            "metrics": _existing(
                _metric("WRBWFRBL", "准备金", scale=Decimal("0.000001"), suffix=" USD tn")
            ),
            "chart_data": _history_rows({"WRBWFRBL": "准备金"}, limit=156),
        },
        {
            "key": "global-dollar",
            "title": "全球美元",
            "summary": "央行美元互换按 settlementDate ≤ as_of < maturityDate 计算在途余额，技术测试单列；跨币种基差仍需授权数据。",
            "metrics": _existing(
                _metric(
                    "FXSWAP-USD-OUTSTANDING",
                    "央行美元互换",
                    decimals=0,
                    suffix=" USD mn",
                ),
                _metric(
                    "FXSWAP-USD-OUTSTANDING-SMALL-VALUE",
                    "其中技术测试",
                    decimals=0,
                    suffix=" USD mn",
                ),
            ),
            "chart_data": _history_rows({"FXSWAP-USD-OUTSTANDING": "在途互换"}, limit=120),
        },
        {
            "key": "subsurface",
            "title": "次表层资金流",
            "summary": "SOFR 尾分位、成交量与常备回购取纽约联储底层数据，IORB 取 Federal Reserve PRATES；早午两场按日合并，小额技术测试不解读为压力。",
            "metrics": _existing(
                *sofr_market_metrics,
                _metric("IORB", "IORB", suffix="%"),
                _derived_metric("sofr-iorb", "SOFR−IORB", "SOFR", "IORB", basis_points=True),
                _metric("SRP", "常备回购", decimals=0, suffix=" USD mn"),
                _metric("SRP-RATE", "常备回购利率", suffix="%"),
            ),
            "chart_data": _sofr_market_history(),
        },
        {
            "key": "auctions",
            "title": "国债拍卖",
            "summary": "拍卖日历、发行额和结果直接来自 Treasury FiscalData；官方源不含 WI yield，因此不发布真实 Tail。",
            "metrics": auction_metrics,
            "chart_data": [
                item["value"] for item in auction_metrics if item["key"] == "latest-bid-cover"
            ],
            "sections": [
                {
                    "title": "近期拍卖",
                    "rows": auction_rows,
                    "fresh_until": _earliest_fresh_until(auction_metrics),
                    "status": (
                        "fresh"
                        if auction_metrics
                        and all(item["quality_status"] == "fresh" for item in auction_metrics)
                        else "stale"
                    ),
                }
            ],
        },
        {
            "key": "economy",
            "title": "经济数据",
            "summary": "就业与通胀指标直接来自 BLS；GDP/PCE 将于 BEA 密钥配置后加入。",
            "metrics": _existing(
                _metric("LNS14000000", "失业率", suffix="%"),
                _metric("CES0000000001", "非农就业", decimals=0, suffix="K"),
                _metric("CUSR0000SA0", "CPI 指数"),
                _metric("CUSR0000SA0L1E", "核心 CPI 指数"),
                _metric("BEA-A191RL", "实际 GDP 增速", suffix="%"),
                _metric("BEA-DPCERL", "实际 PCE 增速", suffix="%"),
            ),
            "chart_data": _history_rows({"LNS14000000": "失业率"}, limit=36),
        },
        {
            "key": "gdp",
            "title": "GDP 与增长",
            "summary": "实际 GDP 与实际 PCE 增速来自 BEA NIPA 1.1.1，季度值为季调年化环比，保留 API production time 和 LastRevised。",
            "metrics": _existing(
                _metric("BEA-A191RL", "实际 GDP 增速", suffix="%"),
                _metric("BEA-DPCERL", "实际 PCE 增速", suffix="%"),
            ),
            "chart_data": _history_rows(
                {"BEA-A191RL": "实际 GDP", "BEA-DPCERL": "实际 PCE"},
                limit=24,
            ),
        },
        {
            "key": "employment",
            "title": "就业",
            "summary": "非农、失业率、时薪和职位空缺均直接来自 BLS 公共 API。",
            "metrics": _existing(
                _metric("CES0000000001", "非农就业", decimals=0, suffix="K"),
                _metric("LNS14000000", "失业率", suffix="%"),
                _metric("CES0500000003", "平均时薪", suffix=" USD"),
                _metric("JTS000000000000000JOL", "职位空缺", decimals=0, suffix="K"),
            ),
            "chart_data": _history_rows(
                {"LNS14000000": "失业率", "CES0500000003": "平均时薪"},
                limit=36,
            ),
        },
        {
            "key": "inflation",
            "title": "通胀",
            "summary": "本页先发布 BLS 官方指数水平；同比/环比将在季调与基期校验后发布。",
            "metrics": _existing(
                _metric("CUSR0000SA0", "CPI 指数"),
                _metric("CUSR0000SA0L1E", "核心 CPI 指数"),
                _metric("WPSFD4", "最终需求 PPI"),
            ),
            "chart_data": _history_rows(
                {
                    "CUSR0000SA0": "CPI",
                    "CUSR0000SA0L1E": "核心 CPI",
                    "WPSFD4": "PPI",
                },
                limit=36,
            ),
        },
        {
            "key": "consumer",
            "title": "消费与零售",
            "summary": "零售与餐饮服务销售来自 Census MRTS，单位为百万美元、季调值；该 API 只提供当前修订口径，不把 fetched_at 冒充 vintage。",
            "metrics": _existing(
                _metric(
                    "CENSUS-MRTS-44X72-SM-SA",
                    "零售与餐饮服务",
                    decimals=0,
                    suffix=" USD mn",
                )
            ),
            "chart_data": _history_rows(
                {"CENSUS-MRTS-44X72-SM-SA": "零售与餐饮服务"},
                limit=36,
            ),
        },
    ]
    with transaction.atomic():
        for definition in definitions:
            snapshot = _publish_dashboard(batch_id=batch_id, **definition)
            if snapshot:
                dashboards.append(snapshot)
    return dashboards


def refresh_official_data(*, current_year: int | None = None) -> dict[str, Any]:
    """Fetch direct official sources, normalize observations, then publish pages."""

    year = current_year or timezone.now().year
    runs: list[IngestionRun] = []
    providers = [
        (
            NYFedMarketsProvider(),
            (
                ("sofr", {"limit": 120}),
                ("effr", {"limit": 120}),
                ("reverse_repo_results", {"limit": 120}),
                ("standing_repo_results", {"limit": 240}),
                ("soma_summary", {"limit": 260}),
                ("usd_fx_swaps", {"limit": 500}),
            ),
        ),
        (
            TreasuryRatesProvider(),
            (("yield_curve", {"year": year}), ("real_yield_curve", {"year": year})),
        ),
        (
            FiscalDataProvider(),
            (
                ("tga", {"page_size": 400}),
                ("treasury_auctions", {"page_size": 1000}, store_treasury_auctions),
            ),
        ),
        (
            BLSProvider(),
            (
                (
                    "series",
                    {"series_ids": BLS_SERIES, "start_year": max(year - 2, 2000), "end_year": year},
                ),
            ),
        ),
        (
            FederalReserveRSSProvider(),
            (
                (
                    "feed",
                    {"feed_name": "press-all", "document_type": "news"},
                    store_fed_documents,
                ),
                (
                    "feed",
                    {"feed_name": "press-monetary", "document_type": "statement"},
                    store_fed_documents,
                ),
                (
                    "feed",
                    {"feed_name": "speeches", "document_type": "speech"},
                    store_fed_documents,
                ),
            ),
        ),
    ]
    try:
        for provider, calls in providers:
            for call in calls:
                method_name, kwargs, *persist_override = call
                result = getattr(provider, method_name)(**kwargs)
                persist = persist_override[0] if persist_override else store_series_observations
                runs.append(record_provider_result(result, persist=persist))
    finally:
        for provider, _ in providers:
            provider.close()
    dashboards = publish_official_dashboards() if _has_publishable_run(runs) else []
    return {
        "runs": [
            {
                "source": run.source.key,
                "dataset": run.dataset,
                "status": run.status,
                "row_count": run.row_count,
                "error": run.error,
            }
            for run in runs
        ],
        "dashboard_keys": [dashboard.key for dashboard in dashboards],
    }


def refresh_h41_data() -> dict[str, Any]:
    """Refresh the large weekly H.4.1 package separately from frequent jobs."""

    provider = FederalReserveH41Provider()
    try:
        result = provider.h41()
        run = record_provider_result(result, persist=_store_h41_observations)
    finally:
        provider.close()
    dashboards = publish_official_dashboards() if _has_publishable_run([run]) else []
    return {
        "runs": [
            {
                "source": run.source.key,
                "dataset": run.dataset,
                "status": run.status,
                "row_count": run.row_count,
                "error": run.error,
                "metadata": run.metadata,
            }
        ],
        "dashboard_keys": [dashboard.key for dashboard in dashboards],
    }


def refresh_prates_data() -> dict[str, Any]:
    """Refresh the Board's daily IORB series separately from the main batch."""

    provider = FederalReservePRATESProvider()
    try:
        result = provider.iorb()
        run = record_provider_result(result, persist=_store_prates_observations)
    finally:
        provider.close()
    dashboards = publish_official_dashboards() if _has_publishable_run([run]) else []
    return {
        "runs": [
            {
                "source": run.source.key,
                "dataset": run.dataset,
                "status": run.status,
                "row_count": run.row_count,
                "error": run.error,
                "metadata": run.metadata,
            }
        ],
        "dashboard_keys": [dashboard.key for dashboard in dashboards],
    }


def refresh_h10_data() -> dict[str, Any]:
    """Refresh Board H.10 daily reference FX data and publish the FX page."""

    provider = FederalReserveH10Provider()
    try:
        result = provider.h10()
        run = record_provider_result(result, persist=_store_h10_observations)
    finally:
        provider.close()
    dashboards = publish_official_dashboards() if _has_publishable_run([run]) else []
    return {
        "runs": [
            {
                "source": run.source.key,
                "dataset": run.dataset,
                "status": run.status,
                "row_count": run.row_count,
                "error": run.error,
                "metadata": run.metadata,
            }
        ],
        "dashboard_keys": [dashboard.key for dashboard in dashboards],
    }


def refresh_credit_official_data() -> dict[str, Any]:
    """Refresh public-display-safe official credit proxies once per day."""

    providers = [
        (FederalReserveSLOOSProvider(), "quarterly_series"),
        (TreasuryHQMProvider(), "par_yields"),
    ]
    runs: list[IngestionRun] = []
    try:
        for provider, method_name in providers:
            result = getattr(provider, method_name)()
            runs.append(record_provider_result(result, persist=store_series_observations))
    finally:
        for provider, _ in providers:
            provider.close()
    dashboards = publish_official_dashboards() if _has_publishable_run(runs) else []
    return {
        "runs": [
            {
                "source": run.source.key,
                "dataset": run.dataset,
                "status": run.status,
                "row_count": run.row_count,
                "error": run.error,
            }
            for run in runs
        ],
        "dashboard_keys": [dashboard.key for dashboard in dashboards],
    }


def refresh_macro_official_data(*, current_year: int | None = None) -> dict[str, Any]:
    """Refresh credential-gated BEA GDP/PCE and Census retail sales."""

    year = current_year or timezone.now().year
    providers = [
        (BEANIPAProvider(), "gdp_pce", {"years": range(max(year - 2, 2000), year + 1)}),
        (
            CensusMRTSProvider(),
            "monthly_retail_sales",
            {"time": f"from {max(year - 2, 2000)}-01"},
        ),
    ]
    runs: list[IngestionRun] = []
    try:
        for provider, method_name, kwargs in providers:
            result = getattr(provider, method_name)(**kwargs)
            runs.append(record_provider_result(result, persist=store_series_observations))
    finally:
        for provider, _, _ in providers:
            provider.close()
    dashboards = publish_official_dashboards() if _has_publishable_run(runs) else []
    return {
        "runs": [
            {
                "source": run.source.key,
                "dataset": run.dataset,
                "status": run.status,
                "row_count": run.row_count,
                "error": run.error,
                "metadata": run.metadata,
            }
            for run in runs
        ],
        "dashboard_keys": [dashboard.key for dashboard in dashboards],
    }
