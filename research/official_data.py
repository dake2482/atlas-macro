"""Fetch and publish public-display-safe official data snapshots.

Every displayed metric keeps its own source and value date. Restricted feeds
are deliberately absent from this module so a public dashboard cannot silently
inherit an internal/test-only observation.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from .calculations import yield_spread
from .models import (
    DashboardSnapshot,
    IngestionRun,
    MetricSnapshot,
    Observation,
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


def _real_observations(series_key: str):
    return (
        Observation.objects.filter(series__key=series_key.lower())
        .exclude(source__key="demo-market")
        .filter(source__licenses__public_display_allowed=True)
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
    return {
        "key": series_key.lower(),
        "label": label,
        "value": float(value),
        "display_value": f"{value:,.{decimals}f}{suffix}",
        "change": round(float(change), decimals) if change is not None else None,
        "unit": suffix,
        "quality_status": latest.quality_status,
        "source": latest.source.name,
        "source_key": latest.source.key,
        "as_of": latest.as_of.isoformat(),
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
    return {
        "key": key,
        "label": label,
        "value": float(value),
        "display_value": f"{value:+,.0f}{suffix}" if basis_points else f"{value:+,.2f}{suffix}",
        "change": None,
        "unit": suffix,
        "quality_status": Observation.Quality.ESTIMATED,
        "source": f"Atlas Macro 计算：{left.source.name} − {right.source.name}",
        "as_of": min(left.as_of, right.as_of).isoformat(),
        "batch_id": f"{left.batch_id},{right.batch_id}",
        "metadata": {"formula": f"{left_key} - {right_key}"},
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


def _auction_snapshot_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    today = timezone.localdate()
    upcoming = list(
        TreasuryAuction.objects.filter(auction_date__gte=today)
        .select_related("source")
        .order_by("auction_date")[:20]
    )
    completed = list(
        TreasuryAuction.objects.filter(
            auction_date__lte=today, bid_to_cover_ratio__isnull=False
        )
        .select_related("source")
        .order_by("-auction_date")[:20]
    )
    metrics: list[dict[str, Any]] = []
    if upcoming:
        item = upcoming[0]
        metrics.append(
            {
                "key": "next-auction",
                "label": "下次拍卖",
                "value": 0,
                "display_value": f"{item.auction_date} · {item.security_term}",
                "change": None,
                "quality_status": item.quality_status,
                "source": item.source.name,
                "source_key": item.source.key,
                "as_of": item.fetched_at.isoformat(),
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
                    "quality_status": item.quality_status,
                    "source": item.source.name,
                    "source_key": item.source.key,
                    "as_of": item.fetched_at.isoformat(),
                    "batch_id": str(item.batch_id),
                }
            )
    if completed:
        item = completed[0]
        metrics.append(
            {
                "key": "latest-bid-cover",
                "label": "最近 Bid-to-Cover",
                "value": float(item.bid_to_cover_ratio),
                "display_value": f"{item.bid_to_cover_ratio:.2f}x",
                "change": None,
                "quality_status": item.quality_status,
                "source": item.source.name,
                "source_key": item.source.key,
                "as_of": item.fetched_at.isoformat(),
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
            "as_of": item.auction_date.isoformat(),
        }
        for item in [*upcoming, *completed]
    ]
    return metrics, rows


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
    quality = (
        Observation.Quality.FRESH
        if all(item.get("quality_status") == Observation.Quality.FRESH for item in metrics)
        else Observation.Quality.ESTIMATED
    )
    source = ensure_source("internal")
    for item in metrics:
        item_value = item.get("value")
        if item_value is None:
            continue
        component_source = (
            Source.objects.filter(key=item.get("source_key", "")).first() or source
        )
        value_date = datetime.fromisoformat(item["as_of"]) if item.get("as_of") else as_of
        if value_date.tzinfo is None:
            value_date = value_date.replace(tzinfo=UTC)
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
                "fetched_at": timezone.now(),
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
        data={
            "demo": False,
            "metrics": metrics,
            "chart_data": chart_data or [item["value"] for item in metrics],
            "sections": sections or [],
            "component_batches": sorted(
                {str(item.get("batch_id")) for item in metrics if item.get("batch_id")}
            ),
        },
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
    auction_metrics, auction_rows = _auction_snapshot_data()
    dashboards: list[DashboardSnapshot] = []
    definitions = [
        {
            "key": "fed-funds",
            "title": "联邦基金利率",
            "summary": "SOFR 与 EFFR 直接来自纽约联储；每个卡片单独标记有效日期。",
            "metrics": _existing(
                _metric("EFFR", "EFFR", suffix="%"),
                _metric("SOFR", "SOFR", suffix="%"),
                _derived_metric("sofr-effr", "SOFR−EFFR", "SOFR", "EFFR", basis_points=True),
            ),
        },
        {
            "key": "rates",
            "title": "利率",
            "summary": "政策利率取纽约联储，国债收益率取美国财政部官方日曲线。",
            "metrics": _existing(
                _metric("EFFR", "EFFR", suffix="%"),
                _metric("SOFR", "SOFR", suffix="%"),
                _metric("UST-2Y", "2Y", suffix="%"),
                _metric("UST-10Y", "10Y", suffix="%"),
                _derived_metric("2s10s", "2s10s", "UST-10Y", "UST-2Y", basis_points=True),
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
            "chart_data": [item["value"] for item in nominal_curve],
            "sections": [{"title": "财政部名义曲线", "rows": nominal_curve, "status": "fresh"}],
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
            "chart_data": [item["value"] for item in real_curve],
            "sections": [{"title": "财政部实际利率曲线", "rows": real_curve, "status": "fresh"}],
        },
        {
            "key": "rrp-tga",
            "title": "RRP 与 TGA",
            "summary": "TGA 为财政部每日财政报表收盘余额；RRP 尚待纽约联储操作端点规范化。",
            "metrics": _existing(_metric("TGA", "TGA 收盘余额", decimals=0, suffix=" USD mn")),
        },
        {
            "key": "auctions",
            "title": "国债拍卖",
            "summary": "拍卖日历、发行额和结果直接来自 Treasury FiscalData；官方源不含 WI yield，因此不发布真实 Tail。",
            "metrics": auction_metrics,
            "chart_data": [
                item["value"] for item in auction_metrics if item["key"] == "latest-bid-cover"
            ],
            "sections": [{"title": "近期拍卖", "rows": auction_rows, "status": "fresh"}],
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
        (NYFedMarketsProvider(), (("sofr", {"limit": 120}), ("effr", {"limit": 120}))),
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
    dashboards = publish_official_dashboards()
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
