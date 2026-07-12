"""Celery entry points for scheduled, lineage-aware refresh jobs."""

from __future__ import annotations

from datetime import date
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .berkshire_letters import refresh_berkshire_letters
from .github_catalog import GITHUB_PROJECT_SEEDS
from .models import DashboardSnapshot, GeneratedAnalysis, IngestionRun
from .official_data import (
    refresh_credit_official_data,
    refresh_h10_data,
    refresh_h41_data,
    refresh_macro_official_data,
    refresh_official_data,
    refresh_prates_data,
)
from .official_news import (
    BLSReleaseProvider,
    SECPressReleaseProvider,
    TreasuryPressReleaseProvider,
    store_official_news,
)
from .providers import CFTCProvider, GitHubProvider, ProviderResult, SECProvider
from .services import (
    record_provider_result,
    store_cftc_positions,
    store_github_repository,
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
    """Refresh direct, public-display-safe official sources and dashboards."""

    return refresh_official_data()


@shared_task(name="research.tasks.refresh_h41_sources")
def refresh_h41_sources() -> dict[str, Any]:
    """Refresh the weekly Federal Reserve H.4.1 DDP archive."""

    return refresh_h41_data()


@shared_task(name="research.tasks.refresh_prates_sources")
def refresh_prates_sources() -> dict[str, Any]:
    """Refresh daily IORB directly from the Federal Reserve PRATES package."""

    return refresh_prates_data()


@shared_task(name="research.tasks.refresh_h10_sources")
def refresh_h10_sources() -> dict[str, Any]:
    """Refresh Board H.10 daily FX reference series."""

    return refresh_h10_data()


@shared_task(name="research.tasks.refresh_credit_official_sources")
def refresh_credit_official_sources() -> dict[str, Any]:
    """Refresh Treasury HQM and Federal Reserve SLOOS official proxies."""

    return refresh_credit_official_data()


@shared_task(
    name="research.tasks.refresh_macro_official_sources",
    soft_time_limit=240,
    time_limit=300,
)
def refresh_macro_official_sources() -> dict[str, Any]:
    """Refresh BEA GDP/PIO and Census retail series from keyless official releases."""

    return refresh_macro_official_data()


@shared_task(name="research.tasks.refresh_crypto_sources")
def refresh_crypto_sources() -> dict[str, Any]:
    """Do not ingest restricted exchange data into the public production database."""

    return summarize_runs(
        [
            _skip(
                "okx",
                "public-market-data",
                "Written public-display and redistribution permission is not configured",
            ),
            _skip(
                "deribit",
                "public-market-data",
                "Written public-display and derived-data permission is not configured",
            ),
        ]
    )


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
    configured_repositories = _setting_list("GITHUB_REPOSITORIES")
    seed_categories = dict(GITHUB_PROJECT_SEEDS)
    repositories = configured_repositories or list(seed_categories)
    provider = GitHubProvider()
    runs = []
    try:
        for repo in repositories:
            result = provider.repository(repo)
            if result.ok:
                for record in result.records:
                    record["category"] = seed_categories.get(repo, "Configured repository")
            runs.append(record_provider_result(result, persist=store_github_repository))
    finally:
        provider.close()
    return summarize_runs(runs)


@shared_task(name="research.tasks.refresh_news_sources")
def refresh_news_sources() -> dict[str, Any]:
    """Refresh metadata-only government feeds from an explicit source whitelist."""

    providers = [
        (SECPressReleaseProvider(), (("press_releases", {}),)),
        (TreasuryPressReleaseProvider(), (("press_releases", {}),)),
        (
            BLSReleaseProvider(),
            tuple(
                ("releases", {"feed_name": feed_name})
                for feed_name in (
                    "employment-situation",
                    "job-openings",
                    "consumer-prices",
                    "producer-prices",
                )
            ),
        ),
    ]
    runs = []
    try:
        for provider, calls in providers:
            for method_name, kwargs in calls:
                result = getattr(provider, method_name)(**kwargs)
                runs.append(record_provider_result(result, persist=store_official_news))
    finally:
        for provider, _ in providers:
            provider.close()
    return summarize_runs(runs)


@shared_task(name="research.tasks.refresh_berkshire_letter_sources")
def refresh_berkshire_letter_sources() -> dict[str, Any]:
    """Refresh first-party shareholder-letter link metadata only."""

    return refresh_berkshire_letters()


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
    provider = CFTCProvider()
    runs = []
    try:
        start_date = f"{max(timezone.localdate().year - 5, 2000)}-01-01"
        for report_type in ("tff-futures", "tff-combined"):
            result = provider.positions(report_type=report_type, start_date=start_date)
            runs.append(record_provider_result(result, persist=store_cftc_positions))
    finally:
        provider.close()
    return summarize_runs(runs)


@shared_task(name="research.tasks.generate_daily_research")
def generate_daily_research() -> dict[str, Any]:
    """Publish a deterministic daily shell only after a complete dashboard batch.

    A model provider can replace this service later.  Until then the generated
    copy is explicitly labelled as a system summary and keeps evidence IDs.
    """

    today = timezone.localdate()
    latest = (
        DashboardSnapshot.objects.filter(is_published=True)
        .exclude(data__demo=True)
        .exclude(source__key="demo-market")
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
