"""Celery entry points for scheduled, lineage-aware refresh jobs."""

from __future__ import annotations

from datetime import date
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import DashboardSnapshot, GeneratedAnalysis, IngestionRun
from .providers import (
    DeribitProvider,
    FREDProvider,
    GitHubProvider,
    OKXProvider,
    ProviderResult,
    SECProvider,
)
from .services import (
    record_provider_result,
    store_fred_observations,
    store_github_repository,
    store_okx_ticker,
    summarize_runs,
)

DEFAULT_FRED_SERIES = (
    "DGS3MO",
    "DGS2",
    "DGS5",
    "DGS10",
    "DGS30",
    "WALCL",
    "RRPONTSYD",
    "WTREGEN",
)


def _setting_list(name: str, default: tuple[str, ...] = ()) -> list[str]:
    value = getattr(settings, name, default)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _skip(source: str, dataset: str, reason: str) -> IngestionRun:
    return record_provider_result(ProviderResult.skip(source, dataset, reason))


@shared_task(name="research.tasks.refresh_official_sources")
def refresh_official_sources() -> dict[str, Any]:
    """Refresh configured FRED series; a missing key records safe partial runs."""

    provider = FREDProvider()
    runs = []
    try:
        for series_id in _setting_list("FRED_SERIES", DEFAULT_FRED_SERIES):
            result = provider.series_observations(series_id, limit=5000)
            runs.append(record_provider_result(result, persist=store_fred_observations))
    finally:
        provider.close()
    return summarize_runs(runs)


@shared_task(name="research.tasks.refresh_crypto_sources")
def refresh_crypto_sources() -> dict[str, Any]:
    """Refresh public BTC spot and option-summary endpoints."""

    runs = []
    okx = OKXProvider()
    try:
        result = okx.ticker(getattr(settings, "OKX_SPOT_INSTRUMENT", "BTC-USDT"))
        runs.append(record_provider_result(result, persist=store_okx_ticker))
    finally:
        okx.close()

    deribit = DeribitProvider()
    try:
        result = deribit.book_summary(currency="BTC", kind="option")
        # The summary is intentionally not forced into the normalized option
        # contract table: it lacks a complete, stable chain snapshot.
        runs.append(record_provider_result(result))
    finally:
        deribit.close()
    return summarize_runs(runs)


@shared_task(name="research.tasks.refresh_filing_sources")
def refresh_filing_sources() -> dict[str, Any]:
    ciks = _setting_list("SEC_CIKS")
    if not ciks:
        return summarize_runs([_skip("sec", "filings", "SEC_CIKS is not configured")])
    provider = SECProvider()
    runs = []
    try:
        for cik in ciks:
            runs.append(record_provider_result(provider.submissions(cik)))
            runs.append(record_provider_result(provider.company_facts(cik)))
    finally:
        provider.close()
    return summarize_runs(runs)


@shared_task(name="research.tasks.refresh_github_sources")
def refresh_github_sources() -> dict[str, Any]:
    repositories = _setting_list("GITHUB_REPOSITORIES")
    if not repositories:
        return summarize_runs(
            [_skip("github", "repositories", "GITHUB_REPOSITORIES is not configured")]
        )
    provider = GitHubProvider()
    runs = []
    try:
        for repo in repositories:
            runs.append(
                record_provider_result(
                    provider.repository(repo), persist=store_github_repository
                )
            )
    finally:
        provider.close()
    return summarize_runs(runs)


@shared_task(name="research.tasks.refresh_news_sources")
def refresh_news_sources() -> dict[str, Any]:
    """Record scheduler health until explicit, licensed RSS feeds are configured."""

    feeds = _setting_list("NEWS_RSS_FEEDS")
    reason = (
        "RSS adapter is intentionally disabled until feed-specific licenses are reviewed"
        if feeds
        else "NEWS_RSS_FEEDS is not configured"
    )
    return summarize_runs([_skip("news-rss", "news", reason)])


@shared_task(name="research.tasks.refresh_market_sources")
def refresh_market_sources() -> dict[str, Any]:
    return summarize_runs(
        [
            _skip(
                "market-data",
                "daily-bars",
                "No production market-data license/provider is configured",
            )
        ]
    )


@shared_task(name="research.tasks.refresh_cftc_sources")
def refresh_cftc_sources() -> dict[str, Any]:
    return summarize_runs(
        [
            _skip(
                "cftc",
                "cot",
                "CFTC PRE dataset identifiers must be configured before ingestion",
            )
        ]
    )


@shared_task(name="research.tasks.generate_daily_research")
def generate_daily_research() -> dict[str, Any]:
    """Publish a deterministic daily shell only after a complete dashboard batch.

    A model provider can replace this service later.  Until then the generated
    copy is explicitly labelled as a system summary and keeps evidence IDs.
    """

    today = timezone.localdate()
    latest = (
        DashboardSnapshot.objects.filter(is_published=True)
        .exclude(quality_status="error")
        .order_by("-as_of")
        .first()
    )
    if latest is None:
        return summarize_runs(
            [_skip("internal", f"daily-research:{today}", "No complete dashboard batch")]
        )

    result = ProviderResult(
        provider="internal",
        dataset=f"daily-research:{today}",
        records=[{"dashboard_id": latest.pk, "batch_id": str(latest.batch_id)}],
        metadata={"dashboard_batch_id": str(latest.batch_id)},
    )

    def persist(_: ProviderResult, __: Any, ___: IngestionRun) -> int:
        GeneratedAnalysis.objects.update_or_create(
            slug=f"daily-system-summary-{today.isoformat()}",
            defaults={
                "title": f"{date.isoformat(today)} 数据批次摘要",
                "body": latest.summary or "当日数据批次已完成，等待人工研判。",
                "model_name": "deterministic-system-summary",
                "prompt_version": "none-v1",
                "generated_at": timezone.now(),
                "review_status": GeneratedAnalysis.ReviewStatus.DRAFT,
                "evidence": [
                    {
                        "type": "dashboard_snapshot",
                        "id": latest.pk,
                        "batch_id": str(latest.batch_id),
                    }
                ],
                "data_as_of": latest.as_of,
                "stale": latest.quality_status == "stale",
            },
        )
        return 1

    return summarize_runs([record_provider_result(result, persist=persist)])
