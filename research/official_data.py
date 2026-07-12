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
from .consumer_credit import FederalReserveG19Provider, NYFedHouseholdDebtProvider
from .credit_official import FederalReserveSLOOSProvider, TreasuryHQMProvider
from .fed_h10 import FederalReserveH10Provider
from .fed_h41 import FederalReserveH41Provider
from .fed_prates import FederalReservePRATESProvider
from .macro_releases import (
    BEAGDPReleaseProvider,
    BEAPIOReleaseProvider,
    CensusMARTSReleaseProvider,
)
from .models import (
    DashboardSnapshot,
    IngestionRun,
    MetricSnapshot,
    Observation,
    RawArtifact,
    ReleaseVintageObservation,
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
    store_release_vintage_observations,
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

CORE_PUBLICATION_KEYS = frozenset(
    {
        "liquidity",
        "transmission-chain",
        "operations",
        "fed-funds",
        "rates",
        "yield-curve",
        "real-rates",
        "rrp-tga",
        "global-dollar",
        "subsurface",
        "auctions",
        "economy",
        "employment",
        "inflation",
    }
)
H41_PUBLICATION_KEYS = frozenset({"liquidity", "fed-balance-sheet", "reserves"})
PRATES_PUBLICATION_KEYS = frozenset(
    {"transmission-chain", "fed-funds", "subsurface"}
)
H10_PUBLICATION_KEYS = frozenset({"assets-fx"})
CREDIT_PUBLICATION_KEYS = frozenset({"credit", "credit-spreads", "credit-stress"})
MACRO_PUBLICATION_GROUPS = {
    "gdp": frozenset({"bea-release"}),
    "consumer": frozenset(
        {
            "census-release",
            "bea-pio-release",
            "federal-reserve-g19",
            "ny-fed-household-credit",
        }
    ),
}
MACRO_REQUIRED_SERIES = {
    "gdp": {
        "bea-release": frozenset(
            {
                "BEA-A191RL",
                "BEA-DPCERL",
                "BEA-GDP-NOMINAL-SAAR",
                "BEA-GDI-REAL-GROWTH-SAAR",
                "BEA-PCE-GOODS-GROWTH",
                "BEA-PCE-SERVICES-GROWTH",
                "BEA-GPDI-GROWTH",
                "BEA-PCE-CONTRIBUTION",
                "BEA-GPDI-CONTRIBUTION",
                "BEA-NET-EXPORTS-CONTRIBUTION",
                "BEA-GOVERNMENT-CONTRIBUTION",
            }
        )
    },
    "consumer": {
        "census-release": frozenset(
            {
                "CENSUS-MRTS-44X72-SM-SA",
                "CENSUS-MRTS-44X72-SM-SA-MOM",
                "CENSUS-MRTS-44X72-SM-SA-YOY",
            }
        ),
        "bea-pio-release": frozenset(
            {
                "BEA-REAL-PCE-MOM",
                "BEA-REAL-DPI-MOM",
                "BEA-PERSONAL-SAVING-RATE",
            }
        ),
        "federal-reserve-g19": frozenset(
            {
                "G19-CONSUMER-CREDIT-OUTSTANDING-SA",
                "G19-REVOLVING-CREDIT-OUTSTANDING-SA",
                "G19-NONREVOLVING-CREDIT-OUTSTANDING-SA",
                "G19-CONSUMER-CREDIT-GROWTH-SAAR",
                "G19-REVOLVING-CREDIT-GROWTH-SAAR",
                "G19-NONREVOLVING-CREDIT-GROWTH-SAAR",
            }
        ),
        "ny-fed-household-credit": frozenset(
            {
                "HHDC-TOTAL-DEBT-BALANCE",
                "HHDC-CREDIT-CARD-BALANCE",
                "HHDC-ALL-90D-DELINQUENT",
                "HHDC-CREDIT-CARD-90D-DELINQUENT",
            }
        ),
    },
}
MACRO_REQUIRED_VINTAGE_SERIES = {
    "gdp": {
        "bea-release": frozenset(
            {
                "BEA-A191RL",
                "BEA-GDP-NOMINAL-SAAR",
                "BEA-GDI-NOMINAL-SAAR",
                "BEA-GDI-REAL-GROWTH-SAAR",
            }
        )
    }
}


def _has_publishable_run(runs: Iterable[IngestionRun]) -> bool:
    """Publish only when the whole refresh group is complete and non-empty."""

    completed = list(runs)
    return bool(completed) and all(
        run.status == IngestionRun.Status.SUCCESS and run.row_count > 0
        for run in completed
    )


def _publishable_keys_for_source_groups(
    runs: Iterable[IngestionRun],
    groups: dict[str, frozenset[str]],
) -> set[str]:
    """Return page keys whose exact source group completed in this refresh."""

    by_source: dict[str, list[IngestionRun]] = {}
    for run in runs:
        by_source.setdefault(run.source.key, []).append(run)
    return {
        page_key
        for page_key, required_sources in groups.items()
        if all(
            len(by_source.get(source_key, [])) == 1
            and _has_publishable_run(by_source[source_key])
            for source_key in required_sources
        )
    }


def _keys_with_current_required_batches(
    page_keys: Iterable[str],
    runs: Iterable[IngestionRun],
) -> set[str]:
    """Bind each page's required latest observations to this refresh's batches."""

    run_by_source = {run.source.key: run for run in runs}
    current: set[str] = set()
    for page_key in page_keys:
        page_requirements = MACRO_REQUIRED_SERIES.get(page_key, {})
        page_is_current = bool(page_requirements)
        for source_key, series_keys in page_requirements.items():
            run = run_by_source.get(source_key)
            if run is None:
                page_is_current = False
                break
            expected_batch = str(run.batch_id)
            for series_key in series_keys:
                observation = _real_observations(series_key).first()
                if (
                    observation is None
                    or observation.source.key != source_key
                    or str(observation.batch_id) != expected_batch
                ):
                    page_is_current = False
                    break
            if not page_is_current:
                break
        for source_key, series_keys in MACRO_REQUIRED_VINTAGE_SERIES.get(
            page_key, {}
        ).items():
            run = run_by_source.get(source_key)
            if run is None:
                page_is_current = False
                break
            stored_series = set(
                ReleaseVintageObservation.objects.filter(
                    source__key=source_key,
                    batch_id=run.batch_id,
                    series__key__in={key.lower() for key in series_keys},
                ).values_list("series__key", flat=True)
            )
            if stored_series != {key.lower() for key in series_keys}:
                page_is_current = False
                break
        if page_is_current:
            current.add(page_key)
    return current


def _mark_latest_dashboards_stale(
    page_keys: Iterable[str],
    runs: Iterable[IngestionRun],
) -> None:
    """Keep the last complete snapshot but expose the failed refresh state."""

    runs_by_source = {run.source.key: run for run in runs}
    checked_at = timezone.now().isoformat()
    with transaction.atomic():
        for page_key in page_keys:
            latest = (
                DashboardSnapshot.objects.select_for_update()
                .filter(key=page_key, is_published=True)
                .order_by("-created_at")
                .first()
            )
            if latest is None:
                continue
            required_sources = MACRO_PUBLICATION_GROUPS.get(page_key, frozenset())
            source_states = []
            for source_key in sorted(required_sources):
                run = runs_by_source.get(source_key)
                source_states.append(
                    {
                        "source": source_key,
                        "status": run.status if run else "missing",
                        "row_count": run.row_count if run else 0,
                        "error": (run.error if run else "source run missing")[:240],
                    }
                )
            data = dict(latest.data or {})
            data["refresh_failure"] = {
                "checked_at": checked_at,
                "reason": (
                    "最近一次必需数据刷新未通过完整性、时序或本批次一致性检查；"
                    "继续保留上一版完整快照。"
                ),
                "sources": source_states,
            }
            latest.data = data
            latest.quality_status = Observation.Quality.STALE
            latest.save(update_fields=["data", "quality_status", "updated_at"])


def _fresh_until(observation: Observation) -> datetime:
    """Return a deadline from the observation period end, not period start."""

    value_date = observation.value_date
    frequency = observation.series.frequency
    release_date = (observation.metadata or {}).get("source_revision_date")
    release_freshness_days = (observation.metadata or {}).get(
        "release_freshness_days"
    )
    if release_date and release_freshness_days:
        try:
            release_deadline = datetime.fromisoformat(str(release_date)).replace(
                tzinfo=UTC
            ) + timedelta(days=int(release_freshness_days))
        except (TypeError, ValueError, OverflowError):
            release_deadline = None
        if release_deadline is not None:
            return release_deadline
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
        .select_related("series", "source", "fallback_source")
        .distinct()
        .order_by("-value_date", "-fetched_at", "-id")
    )


def _latest_observations_by_value_date(
    series_key: str, *, limit: int
) -> list[Observation]:
    """Return one deterministic latest-source observation per economic date."""

    observations: list[Observation] = []
    seen_dates = set()
    for observation in _real_observations(series_key).iterator():
        if observation.value_date in seen_dates:
            continue
        observations.append(observation)
        seen_dates.add(observation.value_date)
        if len(observations) >= limit:
            break
    return observations


def _observation_source_keys(*observations: Observation) -> set[str]:
    keys = {observation.source.key for observation in observations}
    keys.update(
        observation.fallback_source.key
        for observation in observations
        if observation.fallback_source_id
    )
    return keys


def _metric(
    series_key: str,
    label: str,
    *,
    decimals: int = 2,
    suffix: str = "",
    scale: Decimal = Decimal("1"),
) -> dict[str, Any] | None:
    observations = _latest_observations_by_value_date(series_key, limit=2)
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
    source_keys = sorted(_observation_source_keys(latest))
    return {
        "key": series_key.lower(),
        "label": label,
        "value": float(value),
        "display_value": f"{value:,.{decimals}f}{suffix}",
        "change": round(float(change), decimals) if change is not None else None,
        "change_unit": "pp" if suffix == "%" else suffix,
        "unit": suffix,
        "quality_status": quality_status,
        "source": (
            f"{latest.source.name}（备用：{latest.fallback_source.name}）"
            if latest.fallback_source_id
            else latest.source.name
        ),
        "source_key": latest.source.key,
        "source_keys": source_keys,
        "fallback_source": (
            latest.fallback_source.key if latest.fallback_source_id else None
        ),
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
    source_keys = sorted(
        _observation_source_keys(left, right) | {"internal"}
    )
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
        "source_keys": source_keys,
        "as_of": min(left.as_of, right.as_of).isoformat(),
        "value_date": min(left.value_date, right.value_date).isoformat(),
        "fetched_at": max(left.fetched_at, right.fetched_at).isoformat(),
        "fresh_until": fresh_until.isoformat(),
        "batch_id": f"{left.batch_id},{right.batch_id}",
        "metadata": {
            "formula": f"{left_key} - {right_key}",
            "source_keys": sorted(_observation_source_keys(left, right)),
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
    input_source_keys = _observation_source_keys(
        *(observation for _, observation in inputs)
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
        "source_keys": sorted(input_source_keys | {"internal"}),
        "as_of": min(item.as_of for _, item in inputs).isoformat(),
        "value_date": min(item.value_date for _, item in inputs).isoformat(),
        "fetched_at": max(item.fetched_at for _, item in inputs).isoformat(),
        "fresh_until": fresh_until.isoformat(),
        "batch_id": ",".join(str(item.batch_id) for _, item in inputs),
        "metadata": {
            "formula": formula,
            "input_series": [series_key for _, series_key in terms],
            "source_keys": sorted(input_source_keys),
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
        observations = _latest_observations_by_value_date(series_key, limit=limit)
        for observation in reversed(observations):
            day = observation.value_date.date().isoformat()
            row = by_date.setdefault(
                day,
                {"date": day, "_source_keys": [], "_lineage": {}},
            )
            row[label] = float(observation.value)
            source_keys = {observation.source.key}
            fallback_key = None
            if observation.fallback_source_id:
                fallback_key = observation.fallback_source.key
                source_keys.add(fallback_key)
            row["_source_keys"] = sorted(
                {*row["_source_keys"], *source_keys}
            )
            row["_lineage"][label] = {
                "series_key": series_key.lower(),
                "source_key": observation.source.key,
                "source_name": observation.source.name,
                "value_date": observation.value_date.isoformat(),
                "as_of": observation.as_of.isoformat(),
                "fetched_at": observation.fetched_at.isoformat(),
                "batch_id": str(observation.batch_id),
                "quality_status": observation.quality_status,
                "license_scope": observation.source.license_scope,
                "fallback_source": fallback_key,
            }
    return [by_date[day] for day in sorted(by_date)]


def _history_chart(
    *,
    key: str,
    title: str,
    series: dict[str, str],
    limit: int = 120,
    description: str = "",
    kind: str = "line",
) -> dict[str, Any] | None:
    """Build a chart contract with component-level source and freshness metadata."""

    rows = _history_rows(series, limit=limit)
    if not rows:
        return None
    latest = [
        observation
        for series_key in series
        if (observation := _real_observations(series_key).first()) is not None
    ]
    if len(latest) != len(series):
        return None
    deadlines = [_fresh_until(observation) for observation in latest]
    quality_statuses = {observation.quality_status for observation in latest}
    if Observation.Quality.ERROR in quality_statuses:
        quality_status = Observation.Quality.ERROR
    elif timezone.now() > min(deadlines) or Observation.Quality.STALE in quality_statuses:
        quality_status = Observation.Quality.STALE
    elif Observation.Quality.FALLBACK in quality_statuses:
        quality_status = Observation.Quality.FALLBACK
    elif quality_statuses == {Observation.Quality.FRESH}:
        quality_status = Observation.Quality.FRESH
    else:
        quality_status = Observation.Quality.ESTIMATED
    source_keys = {
        source_key
        for observation in latest
        for source_key in (
            observation.source.key,
            observation.fallback_source.key if observation.fallback_source_id else None,
        )
        if source_key
    }
    return {
        "key": key,
        "title": title,
        "description": description,
        "kind": kind,
        "data": rows,
        "source_keys": sorted(source_keys),
        "as_of": min(observation.as_of for observation in latest).isoformat(),
        "fetched_at": max(observation.fetched_at for observation in latest).isoformat(),
        "fresh_until": min(deadlines).isoformat(),
        "quality_status": quality_status,
        "batch_ids": sorted({str(observation.batch_id) for observation in latest}),
    }


def _gdp_vintage_chart_and_section() -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    """Build the public GDP revision trail from one complete BEA workbook batch."""

    latest_run = (
        IngestionRun.objects.filter(
            source__key="bea-release",
            dataset="gdp-release-workbooks",
            status=IngestionRun.Status.SUCCESS,
        )
        .order_by("-completed_at", "-id")
        .first()
    )
    if latest_run is None:
        return None, None
    vintages = list(
        ReleaseVintageObservation.objects.filter(
            source=latest_run.source,
            series__key="bea-a191rl",
            batch_id=latest_run.batch_id,
        )
        .filter(public_display_license_q())
        .select_related("series", "source", "fallback_source")
        .order_by("value_date", "release_date", "id")
    )
    if not vintages:
        return None, None
    periods: dict[datetime, list[ReleaseVintageObservation]] = {}
    for item in vintages:
        periods.setdefault(item.value_date, []).append(item)
    latest_period = max(periods)
    current = (
        Observation.objects.filter(
            source=latest_run.source,
            series__key="bea-a191rl",
            batch_id=latest_run.batch_id,
            value_date=latest_period,
        )
        .select_related("series", "source", "fallback_source")
        .first()
    )
    if current is None:
        return None, None
    fresh_until = _fresh_until(current)
    quality_status = current.quality_status
    if timezone.now() > fresh_until and quality_status == Observation.Quality.FRESH:
        quality_status = Observation.Quality.STALE

    def lineage(item: ReleaseVintageObservation) -> dict[str, Any]:
        return {
            "series_key": item.series.key,
            "source_key": item.source.key,
            "source_name": item.source.name,
            "value_date": item.value_date.isoformat(),
            "as_of": item.as_of.isoformat(),
            "release_date": item.release_date.isoformat(),
            "estimate_round": item.estimate_round,
            "fetched_at": item.fetched_at.isoformat(),
            "batch_id": str(item.batch_id),
            "quality_status": item.quality_status,
            "license_scope": item.license_scope,
            "fallback_source": (
                item.fallback_source.key if item.fallback_source_id else None
            ),
        }

    latest_entries = periods[latest_period]
    chart_rows = [
        {
            "date": f"{item.vintage_label}\n{item.release_date:%m-%d}",
            "实际 GDP": float(item.value),
            "_source_keys": [item.source.key],
            "_lineage": {"实际 GDP": lineage(item)},
        }
        for item in latest_entries
    ]
    latest_item = latest_entries[-1]
    quarter_label = (
        f"{latest_period.year}Q{((latest_period.month - 1) // 3) + 1}"
    )
    chart = {
        "key": "gdp-vintage-trail",
        "title": f"{quarter_label} 实际 GDP 估算修订",
        "description": "按 BEA 官方发布日期展示每轮季调年化环比估算，单位：%。",
        "kind": "line",
        "panel_class": "lg:col-span-2",
        "data": chart_rows,
        "source_keys": [latest_run.source.key],
        "as_of": latest_item.as_of.isoformat(),
        "fetched_at": max(item.fetched_at for item in latest_entries).isoformat(),
        "fresh_until": fresh_until.isoformat(),
        "quality_status": quality_status,
        "batch_ids": [str(latest_run.batch_id)],
    }

    section_rows = []
    for period in sorted(periods, reverse=True)[:8]:
        entries = periods[period]
        first, latest = entries[0], entries[-1]
        revision = latest.value - first.value
        labels = " → ".join(item.vintage_label for item in entries)
        values = " → ".join(f"{item.value:.2f}%" for item in entries)
        release_path = " · ".join(
            f"{item.vintage_label} {item.release_date.isoformat()}" for item in entries
        )
        section_rows.append(
            {
                "label": f"{period.year}Q{((period.month - 1) // 3) + 1}",
                "display_value": values,
                "status": f"{labels}；累计修订 {revision:+.2f}pp",
                "description": release_path,
                "source": latest.source.name,
                "source_key": latest.source.key,
                "source_keys": [latest.source.key],
                "as_of": latest.as_of.isoformat(),
                "fetched_at": latest.fetched_at.isoformat(),
                "quality_status": latest.quality_status,
                "license_scope": latest.license_scope,
                "fallback_source": (
                    latest.fallback_source.key if latest.fallback_source_id else None
                ),
                "batch_id": str(latest.batch_id),
            }
        )
    section = {
        "title": "GDP 发布轮次与修订路径",
        "description": (
            f"当前官方工作簿保留 {len(vintages):,} 条实际 GDP 发布记录；"
            "表格展示最近 8 个观察季度，箭头严格按发布日期排序。"
        ),
        "rows": section_rows,
        "status": quality_status,
        "full_width": True,
        "source_key": latest_run.source.key,
        "source_keys": [latest_run.source.key],
        "as_of": latest_item.as_of.isoformat(),
        "fetched_at": latest_item.fetched_at.isoformat(),
        "fresh_until": fresh_until.isoformat(),
        "quality_status": quality_status,
        "batch_id": str(latest_run.batch_id),
    }
    return chart, section


def _earliest_fresh_until(rows: Iterable[dict[str, Any]]) -> str | None:
    return min(
        (item["fresh_until"] for item in rows if item.get("fresh_until")),
        default=None,
    )


def _sofr_market_metrics() -> list[dict[str, Any]]:
    observations = _latest_observations_by_value_date("SOFR", limit=2)
    if not observations:
        return []
    latest = observations[0]
    previous = observations[1] if len(observations) > 1 else None
    fresh_until = _fresh_until(latest)
    quality = Observation.Quality.STALE if timezone.now() > fresh_until else latest.quality_status
    latest_source_keys = sorted(_observation_source_keys(latest))
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
                "change_unit": "pp" if suffix == "%" else suffix,
                "unit": suffix,
                "quality_status": quality,
                "source": (
                    f"{latest.source.name}（备用：{latest.fallback_source.name}）"
                    if latest.fallback_source_id
                    else latest.source.name
                ),
                "source_key": latest.source.key,
                "source_keys": latest_source_keys,
                "fallback_source": (
                    latest.fallback_source.key
                    if latest.fallback_source_id
                    else None
                ),
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
                "source_keys": sorted(
                    _observation_source_keys(latest) | {"internal"}
                ),
                "as_of": latest.as_of.isoformat(),
                "value_date": latest.value_date.isoformat(),
                "fetched_at": latest.fetched_at.isoformat(),
                "fresh_until": fresh_until.isoformat(),
                "batch_id": str(latest.batch_id),
                "metadata": {
                    "formula": "SOFR percentPercentile99 - percentRate",
                    "source_keys": sorted(_observation_source_keys(latest)),
                },
            }
        )
        iorb = _real_observations("IORB").first()
        if iorb is not None:
            iorb_tail = (Decimal(str(percentile_99)) - iorb.value) * Decimal("100")
            iorb_fresh_until = min(fresh_until, _fresh_until(iorb))
            input_source_keys = _observation_source_keys(latest, iorb)
            source_keys = sorted(input_source_keys | {"internal"})
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
                        "source_keys": sorted(input_source_keys),
                    },
                }
            )
    return metrics


def _sofr_market_history(*, limit: int = 120) -> list[dict[str, Any]]:
    rows = []
    for observation in reversed(
        _latest_observations_by_value_date("SOFR", limit=limit)
    ):
        row: dict[str, Any] = {
            "date": observation.value_date.date().isoformat(),
            "SOFR": float(observation.value),
            "_source_keys": sorted(_observation_source_keys(observation)),
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


def _store_release_workbook_observations(result, source, run) -> int:
    """Persist normalized release rows plus immutable HTML/XLSX fingerprints."""

    incoming_series = {
        str(record.get("series_id") or "").lower()
        for record in result.records
        if record.get("series_id") and record.get("date")
    }
    incoming_dates = [
        datetime.fromisoformat(str(record["date"])[:10])
        for record in result.records
        if record.get("series_id") and record.get("date")
    ]
    existing_latest = (
        Observation.objects.filter(source=source, series__key__in=incoming_series)
        .order_by("-value_date")
        .first()
    )
    if (
        incoming_dates
        and existing_latest is not None
        and max(incoming_dates).date() < existing_latest.value_date.date()
    ):
        raise ValueError(
            "release latest value date regressed behind the stored official source"
        )
    row_count = store_series_observations(result, source, run)
    vintage_count = store_release_vintage_observations(result, source, run)
    if result.dataset == "gdp-release-workbooks" and vintage_count == 0:
        raise ValueError("BEA GDP release contained no persistable vintage observations")
    row_count += vintage_count
    for artifact in result.metadata.get("artifacts", []):
        url = str(artifact.get("url") or "")
        digest = str(artifact.get("sha256") or "")
        if not url or not digest:
            continue
        RawArtifact.objects.create(
            run=run,
            uri=f"{url}#sha256={digest}",
            sha256=digest,
            content_type=str(artifact.get("content_type") or "application/octet-stream"),
            size_bytes=int(artifact.get("size") or 0),
        )
    return row_count


def _publish_dashboard(
    *,
    key: str,
    title: str,
    summary: str,
    metrics: list[dict[str, Any]],
    chart_data: Any = None,
    charts: list[dict[str, Any]] | None = None,
    sections: list[dict[str, Any]] | None = None,
    required_metric_keys: frozenset[str] | None = None,
    batch_id: uuid.UUID,
) -> DashboardSnapshot | None:
    if not metrics:
        return None
    if required_metric_keys and not required_metric_keys <= {
        str(item.get("key") or "") for item in metrics
    }:
        return None

    def payload_source_keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            keys = {str(value["source_key"])} if value.get("source_key") else set()
            for fallback_field in ("fallback_source", "fallback_source_key"):
                if value.get(fallback_field):
                    keys.add(str(value[fallback_field]))
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

    def payload_batch_ids(value: Any) -> set[str]:
        def normalized(raw: Any) -> set[str]:
            return {
                item.strip()
                for item in str(raw or "").split(",")
                if item.strip()
            }

        if isinstance(value, dict):
            batches = normalized(value.get("batch_id"))
            for item in value.get("batch_ids", []):
                batches.update(normalized(item))
            for nested in value.values():
                batches.update(payload_batch_ids(nested))
            return batches
        if isinstance(value, list):
            batches: set[str] = set()
            for nested in value:
                batches.update(payload_batch_ids(nested))
            return batches
        return set()

    normalized_charts = [dict(item) for item in charts or [] if item]
    if not normalized_charts:
        inherited_source_keys = payload_source_keys(chart_data or [])
        if not inherited_source_keys:
            inherited_source_keys = payload_source_keys(metrics)
        metric_qualities = {item.get("quality_status") for item in metrics}
        if Observation.Quality.ERROR in metric_qualities:
            inherited_quality = Observation.Quality.ERROR
        elif Observation.Quality.STALE in metric_qualities:
            inherited_quality = Observation.Quality.STALE
        elif Observation.Quality.FALLBACK in metric_qualities:
            inherited_quality = Observation.Quality.FALLBACK
        elif metric_qualities == {Observation.Quality.FRESH}:
            inherited_quality = Observation.Quality.FRESH
        else:
            inherited_quality = Observation.Quality.ESTIMATED
        normalized_charts = [
            {
                "key": "primary",
                "title": "核心趋势",
                "description": "",
                "kind": "line",
                "data": chart_data or [],
                "source_keys": sorted(inherited_source_keys),
                "as_of": min(
                    (item["as_of"] for item in metrics if item.get("as_of")),
                    default=None,
                ),
                "fetched_at": max(
                    (item["fetched_at"] for item in metrics if item.get("fetched_at")),
                    default=None,
                ),
                "fresh_until": min(
                    (item["fresh_until"] for item in metrics if item.get("fresh_until")),
                    default=None,
                ),
                "quality_status": inherited_quality,
                "batch_ids": sorted(payload_batch_ids(metrics)),
            }
        ]
    for chart in normalized_charts:
        chart.setdefault("data", [])
        chart.setdefault("kind", "line")
        chart.setdefault("title", "趋势")

    as_of_values = [
        datetime.fromisoformat(item["as_of"])
        for item in [*metrics, *normalized_charts]
        if item.get("as_of")
    ]
    as_of = min(as_of_values) if as_of_values else timezone.now()
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    component_qualities = {
        item.get("quality_status") for item in [*metrics, *normalized_charts]
    }
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
        payload_batch_ids([metrics, normalized_charts, sections or []])
    )
    source_keys = sorted(
        payload_source_keys([metrics, normalized_charts, sections or []])
    )
    snapshot_data = {
        "demo": False,
        "metrics": metrics,
        "charts": normalized_charts,
        "chart_data": normalized_charts[0]["data"],
        "sections": sections or [],
        "component_batches": component_batches,
        "source_keys": source_keys,
        "required_notices": public_source_notices(source_keys),
        "fresh_until": min(
            (
                item["fresh_until"]
                for item in [*metrics, *normalized_charts, *(sections or [])]
                if item.get("fresh_until")
            ),
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
                    "batch_ids",
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
        latest_data = dict(latest.data or {})
        refresh_failure = latest_data.pop("refresh_failure", None)
        if refresh_failure or latest.quality_status != quality:
            latest.data = latest_data
            latest.quality_status = quality
            latest.save(update_fields=["data", "quality_status", "updated_at"])
        return None
    for item in metrics:
        item_value = item.get("value")
        if item_value is None:
            continue
        component_source = Source.objects.filter(key=item.get("source_key", "")).first() or source
        component_fallback_source = Source.objects.filter(
            key=item.get("fallback_source", "")
        ).first()
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
                "fallback_source": component_fallback_source,
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


def publish_official_dashboards(
    *, keys: Iterable[str] | None = None
) -> list[DashboardSnapshot]:
    """Atomically publish only the dashboards affected by a completed source batch."""

    batch_id = uuid.uuid4()
    selected_keys = set(keys) if keys is not None else None
    nominal_curve = _curve_rows(
        "ust", ("1m", "2m", "3m", "4m", "6m", "1y", "2y", "3y", "5y", "7y", "10y", "20y", "30y")
    )
    real_curve = _curve_rows("tips", ("5y", "7y", "10y", "20y", "30y"))
    hqm_curve = _curve_rows("hqm-par", ("2y", "5y", "10y", "30y"))
    sofr_market_metrics = _sofr_market_metrics()
    auction_metrics, auction_rows = _auction_snapshot_data()
    consumer_metrics: list[dict[str, Any]] = []
    consumer_charts: list[dict[str, Any]] = []
    gdp_vintage_chart: dict[str, Any] | None = None
    gdp_vintage_section: dict[str, Any] | None = None
    if selected_keys is None or "gdp" in selected_keys:
        gdp_vintage_chart, gdp_vintage_section = _gdp_vintage_chart_and_section()
    if selected_keys is None or "consumer" in selected_keys:
        consumer_metrics = _existing(
            _metric(
                "CENSUS-MRTS-44X72-SM-SA",
                "零售与餐饮服务",
                decimals=0,
                suffix=" USD mn",
            ),
            _metric(
                "CENSUS-MRTS-44X72-SM-SA-MOM",
                "零售环比",
                suffix="%",
            ),
            _metric(
                "CENSUS-MRTS-44X72-SM-SA-YOY",
                "零售同比",
                suffix="%",
            ),
            _metric("BEA-REAL-PCE-MOM", "实际 PCE 环比", suffix="%"),
            _metric("BEA-PERSONAL-SAVING-RATE", "个人储蓄率", suffix="%"),
            _metric("BEA-REAL-DPI-MOM", "实际可支配收入环比", suffix="%"),
            _metric(
                "G19-CONSUMER-CREDIT-OUTSTANDING-SA",
                "G.19 消费者信贷余额",
                scale=Decimal("0.000001"),
                suffix=" USD tn",
            ),
            _metric(
                "G19-CONSUMER-CREDIT-GROWTH-SAAR",
                "G.19 信贷增速",
                suffix="%",
            ),
            _metric(
                "G19-REVOLVING-CREDIT-GROWTH-SAAR",
                "循环信贷增速",
                suffix="%",
            ),
            _metric(
                "G19-NONREVOLVING-CREDIT-GROWTH-SAAR",
                "非循环信贷增速",
                suffix="%",
            ),
            _metric("HHDC-TOTAL-DEBT-BALANCE", "家庭债务余额", suffix=" USD tn"),
            _metric("HHDC-CREDIT-CARD-BALANCE", "信用卡余额", suffix=" USD tn"),
            _metric("HHDC-ALL-90D-DELINQUENT", "全部债务 90+ 天逾期", suffix="%"),
            _metric(
                "HHDC-CREDIT-CARD-90D-DELINQUENT",
                "信用卡 90+ 天逾期",
                suffix="%",
            ),
        )
        consumer_charts = [
            chart
            for chart in (
                _history_chart(
                    key="retail-sales",
                    title="零售与餐饮服务销售",
                    description="季调月度水平，单位：百万美元",
                    series={"CENSUS-MRTS-44X72-SM-SA": "零售与餐饮服务"},
                    limit=36,
                ),
                _history_chart(
                    key="real-consumption-income-momentum",
                    title="实际消费与收入动能",
                    description="实际 PCE 与实际可支配收入月环比，单位：%",
                    series={
                        "BEA-REAL-PCE-MOM": "实际 PCE 环比",
                        "BEA-REAL-DPI-MOM": "实际 DPI 环比",
                    },
                    limit=120,
                ),
                _history_chart(
                    key="personal-saving-rate",
                    title="个人储蓄率",
                    description="个人储蓄占可支配个人收入，单位：%",
                    series={"BEA-PERSONAL-SAVING-RATE": "个人储蓄率"},
                    limit=120,
                ),
                _history_chart(
                    key="consumer-credit-composition",
                    title="G.19 消费者信贷结构",
                    description=(
                        "季调月度余额，单位：百万美元；"
                        "不含以房地产抵押的贷款"
                    ),
                    series={
                        "G19-REVOLVING-CREDIT-OUTSTANDING-SA": "循环信贷",
                        "G19-NONREVOLVING-CREDIT-OUTSTANDING-SA": "非循环信贷",
                    },
                    limit=120,
                ),
                _history_chart(
                    key="household-debt-composition",
                    title="家庭债务结构",
                    description=(
                        "纽约联储 Consumer Credit Panel / Equifax 季度数据，"
                        "单位：万亿美元"
                    ),
                    series={
                        "HHDC-MORTGAGE-BALANCE": "抵押贷款",
                        "HHDC-HELOC-BALANCE": "HELOC",
                        "HHDC-AUTO-LOAN-BALANCE": "汽车贷款",
                        "HHDC-CREDIT-CARD-BALANCE": "信用卡",
                        "HHDC-STUDENT-LOAN-BALANCE": "学生贷款",
                    },
                    limit=96,
                ),
                _history_chart(
                    key="household-debt-delinquency",
                    title="90+ 天严重逾期率",
                    description="占各类债务余额的比例，单位：%",
                    series={
                        "HHDC-ALL-90D-DELINQUENT": "全部债务",
                        "HHDC-CREDIT-CARD-90D-DELINQUENT": "信用卡",
                        "HHDC-AUTO-90D-DELINQUENT": "汽车贷款",
                        "HHDC-MORTGAGE-90D-DELINQUENT": "抵押贷款",
                    },
                    limit=96,
                ),
            )
            if chart is not None
        ]
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
            "summary": "本总览只聚合同一 BLS 刷新批次的就业与通胀指标；GDP/PCE 在独立页面按 BEA 批次发布。",
            "metrics": _existing(
                _metric("LNS14000000", "失业率", suffix="%"),
                _metric("CES0000000001", "非农就业", decimals=0, suffix="K"),
                _metric("CUSR0000SA0", "CPI 指数"),
                _metric("CUSR0000SA0L1E", "核心 CPI 指数"),
            ),
            "chart_data": _history_rows({"LNS14000000": "失业率"}, limit=36),
        },
        {
            "key": "gdp",
            "title": "GDP 与增长",
            "summary": "实际 GDP、GDI、PCE、分项增速与贡献均来自 BEA 官方发布工作簿；当前指标取每季度最新轮次，独立 vintage 数据层同时保留 Advance、Second、Third 与后续 Revised 的完整修订路径。",
            "metrics": _existing(
                _metric("BEA-A191RL", "实际 GDP 增速", suffix="%"),
                _metric("BEA-DPCERL", "实际 PCE 增速", suffix="%"),
                _metric("BEA-GDP-NOMINAL-SAAR", "名义 GDP", decimals=1, suffix=" USD bn"),
                _metric("BEA-GDI-REAL-GROWTH-SAAR", "实际 GDI 增速", suffix="%"),
                _metric("BEA-PCE-GOODS-GROWTH", "商品消费增速", suffix="%"),
                _metric("BEA-PCE-SERVICES-GROWTH", "服务消费增速", suffix="%"),
                _metric("BEA-GPDI-GROWTH", "私人国内投资增速", suffix="%"),
                _metric("BEA-PCE-CONTRIBUTION", "消费贡献", suffix="pp"),
                _metric("BEA-GPDI-CONTRIBUTION", "投资贡献", suffix="pp"),
                _metric(
                    "BEA-NET-EXPORTS-CONTRIBUTION",
                    "净出口贡献",
                    suffix="pp",
                ),
                _metric("BEA-GOVERNMENT-CONTRIBUTION", "政府贡献", suffix="pp"),
            ),
            "charts": _existing(
                _history_chart(
                    key="gdp-growth-history",
                    title="实际 GDP 与实际 PCE 增速",
                    description="季调年化环比，单位：%。",
                    series={
                        "BEA-A191RL": "实际 GDP",
                        "BEA-DPCERL": "实际 PCE",
                    },
                    limit=24,
                )
                or _history_chart(
                    key="gdp-growth-history",
                    title="实际 GDP 增速",
                    description="季调年化环比，单位：%。",
                    series={"BEA-A191RL": "实际 GDP"},
                    limit=24,
                ),
                gdp_vintage_chart,
            ),
            "sections": _existing(gdp_vintage_section),
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
            "summary": (
                "零售与餐饮服务销售来自 Census MARTS 官方发布工作簿；实际 PCE、"
                "实际可支配收入和个人储蓄率来自 BEA 月度 PIO Section 2 工作簿，"
                "并与当月 Historical Comparisons 摘要交叉校验。消费者信贷来自"
                "联储 G.19，家庭债务和逾期率来自 New York Fed Consumer Credit "
                "Panel / Equifax；总量数据不用于推断特定收入群体的压力。消费者"
                "信心因公开再发布许可未就绪，继续保留采购标记。"
            ),
            "metrics": consumer_metrics,
            "charts": consumer_charts,
            "required_metric_keys": frozenset(
                {
                    "census-mrts-44x72-sm-sa",
                    "census-mrts-44x72-sm-sa-mom",
                    "census-mrts-44x72-sm-sa-yoy",
                    "bea-real-pce-mom",
                    "bea-personal-saving-rate",
                    "bea-real-dpi-mom",
                }
            ),
        },
    ]
    with transaction.atomic():
        for definition in definitions:
            if selected_keys is not None and definition["key"] not in selected_keys:
                continue
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
    dashboards = (
        publish_official_dashboards(keys=CORE_PUBLICATION_KEYS)
        if _has_publishable_run(runs)
        else []
    )
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
    dashboards = (
        publish_official_dashboards(keys=H41_PUBLICATION_KEYS)
        if _has_publishable_run([run])
        else []
    )
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
    dashboards = (
        publish_official_dashboards(keys=PRATES_PUBLICATION_KEYS)
        if _has_publishable_run([run])
        else []
    )
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
    dashboards = (
        publish_official_dashboards(keys=H10_PUBLICATION_KEYS)
        if _has_publishable_run([run])
        else []
    )
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
    dashboards = (
        publish_official_dashboards(keys=CREDIT_PUBLICATION_KEYS)
        if _has_publishable_run(runs)
        else []
    )
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
    """Refresh keyless growth and consumer releases with page-level quality gates."""

    _ = current_year  # Backward-compatible command/task signature.
    providers = [
        (
            BEAGDPReleaseProvider(),
            "gdp_pce",
            {},
            _store_release_workbook_observations,
        ),
        (
            CensusMARTSReleaseProvider(),
            "monthly_retail_sales",
            {},
            _store_release_workbook_observations,
        ),
        (
            BEAPIOReleaseProvider(),
            "personal_income_outlays",
            {},
            _store_release_workbook_observations,
        ),
        (
            FederalReserveG19Provider(),
            "consumer_credit",
            {},
            _store_release_workbook_observations,
        ),
        (
            NYFedHouseholdDebtProvider(),
            "household_debt",
            {},
            _store_release_workbook_observations,
        ),
    ]
    runs: list[IngestionRun] = []
    try:
        for provider, method_name, kwargs, persist in providers:
            result = getattr(provider, method_name)(**kwargs)
            runs.append(record_provider_result(result, persist=persist))
    finally:
        for provider, _, _, _ in providers:
            provider.close()
    completed_keys = _publishable_keys_for_source_groups(
        runs, MACRO_PUBLICATION_GROUPS
    )
    publishable_keys = _keys_with_current_required_batches(completed_keys, runs)
    stale_keys = set(MACRO_PUBLICATION_GROUPS) - publishable_keys
    _mark_latest_dashboards_stale(stale_keys, runs)
    dashboards = (
        publish_official_dashboards(keys=publishable_keys)
        if publishable_keys
        else []
    )
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
        "stale_dashboard_keys": sorted(stale_keys),
    }
