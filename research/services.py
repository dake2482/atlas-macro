"""Application services for lineage-aware ingestion and data access."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import (
    CFTCPosition,
    FedDocument,
    GitHubProject,
    IngestionRun,
    Instrument,
    Observation,
    QualityCheck,
    RawArtifact,
    SeriesDefinition,
    Source,
    SourceLicense,
    TreasuryAuction,
)
from .providers import ProviderResult

SOURCE_CATALOG: dict[str, dict[str, Any]] = {
    "fred": {
        "name": "Federal Reserve Economic Data",
        "homepage": "https://fred.stlouisfed.org/",
        "kind": "aggregator",
        "license_status": Source.LicenseStatus.REVIEW,
        "license_scope": "Each series retains its upstream owner's rights; no blanket public redistribution",
        "redistribution_allowed": False,
        "public_display_allowed": False,
        "derived_display_allowed": False,
        "historical_storage_allowed": False,
        "ai_use_allowed": False,
        "terms_url": "https://fred.stlouisfed.org/docs/api/terms_of_use.html",
        "attribution": "Federal Reserve Bank of St. Louis",
    },
    "ny-fed-markets": {
        "name": "Federal Reserve Bank of New York Markets Data",
        "homepage": "https://markets.newyorkfed.org/static/docs/markets-api.html",
        "kind": "official",
        "license_status": Source.LicenseStatus.OPEN,
        "license_scope": "Attributed official reference-rate display; NY Fed disclaimer applies",
        "redistribution_allowed": True,
        "public_display_allowed": True,
        "derived_display_allowed": True,
        "historical_storage_allowed": True,
        "ai_use_allowed": True,
        "terms_url": "https://www.newyorkfed.org/privacy/termsofuse",
        "attribution": "Federal Reserve Bank of New York",
    },
    "us-treasury-rates": {
        "name": "U.S. Treasury Daily Interest Rates",
        "homepage": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/",
        "kind": "official",
        "license_status": Source.LicenseStatus.OPEN,
        "license_scope": "Attributed U.S. government data",
        "redistribution_allowed": True,
        "public_display_allowed": True,
        "derived_display_allowed": True,
        "historical_storage_allowed": True,
        "ai_use_allowed": True,
        "attribution": "U.S. Department of the Treasury",
    },
    "treasury-fiscal-data": {
        "name": "U.S. Treasury FiscalData",
        "homepage": "https://fiscaldata.treasury.gov/",
        "kind": "official",
        "license_status": Source.LicenseStatus.OPEN,
        "license_scope": "Attributed U.S. government fiscal data",
        "redistribution_allowed": True,
        "public_display_allowed": True,
        "derived_display_allowed": True,
        "historical_storage_allowed": True,
        "ai_use_allowed": True,
        "attribution": "U.S. Department of the Treasury, FiscalData",
    },
    "bls": {
        "name": "U.S. Bureau of Labor Statistics",
        "homepage": "https://www.bls.gov/developers/",
        "kind": "official",
        "license_status": Source.LicenseStatus.OPEN,
        "license_scope": "Public BLS data; access date and non-endorsement disclaimer required",
        "redistribution_allowed": True,
        "public_display_allowed": True,
        "derived_display_allowed": True,
        "historical_storage_allowed": True,
        "ai_use_allowed": True,
        "terms_url": "https://www.bls.gov/developers/termsOfService.htm",
        "attribution": "U.S. Bureau of Labor Statistics",
    },
    "cftc": {
        "name": "CFTC Public Reporting Environment",
        "homepage": "https://publicreporting.cftc.gov/",
        "kind": "official",
        "license_status": Source.LicenseStatus.OPEN,
        "license_scope": "Attributed official COT public reporting data",
        "redistribution_allowed": True,
        "public_display_allowed": True,
        "derived_display_allowed": True,
        "historical_storage_allowed": True,
        "ai_use_allowed": True,
        "attribution": "U.S. Commodity Futures Trading Commission",
    },
    "federal-reserve": {
        "name": "Federal Reserve Board",
        "homepage": "https://www.federalreserve.gov/",
        "kind": "official",
        "license_status": Source.LicenseStatus.OPEN,
        "license_scope": "Attributed official document metadata and public releases",
        "redistribution_allowed": True,
        "public_display_allowed": True,
        "derived_display_allowed": True,
        "historical_storage_allowed": True,
        "ai_use_allowed": True,
        "attribution": "Board of Governors of the Federal Reserve System",
    },
    "sec": {
        "name": "SEC EDGAR",
        "homepage": "https://www.sec.gov/edgar",
        "kind": "official",
        "license_status": Source.LicenseStatus.OPEN,
        "license_scope": "Public filings; issuer material retains its own rights",
        "redistribution_allowed": True,
        "public_display_allowed": True,
        "derived_display_allowed": True,
        "historical_storage_allowed": True,
        "ai_use_allowed": True,
        "attribution": "U.S. Securities and Exchange Commission",
    },
    "github": {
        "name": "GitHub REST API",
        "homepage": "https://docs.github.com/en/rest",
        "kind": "public-api",
        "license_status": Source.LicenseStatus.REVIEW,
        "license_scope": "Metadata only; repository licenses apply separately",
        "redistribution_allowed": False,
        "public_display_allowed": True,
        "derived_display_allowed": True,
        "historical_storage_allowed": True,
        "ai_use_allowed": False,
        "attribution": "GitHub",
    },
    "okx": {
        "name": "OKX Public Market Data",
        "homepage": "https://www.okx.com/docs-v5/",
        "kind": "public-api",
        "license_status": Source.LicenseStatus.REVIEW,
        "license_scope": "Internal testing only unless OKX grants written public-display permission",
        "redistribution_allowed": False,
        "public_display_allowed": False,
        "derived_display_allowed": False,
        "historical_storage_allowed": False,
        "ai_use_allowed": False,
        "terms_url": "https://www.okx.com/en-us/help/okx-api-agreement",
        "attribution": "OKX",
    },
    "deribit": {
        "name": "Deribit Public API",
        "homepage": "https://docs.deribit.com/",
        "kind": "public-api",
        "license_status": Source.LicenseStatus.REVIEW,
        "license_scope": "Personal/internal testing only unless Deribit grants written permission",
        "redistribution_allowed": False,
        "public_display_allowed": False,
        "derived_display_allowed": False,
        "historical_storage_allowed": False,
        "ai_use_allowed": False,
        "terms_url": "https://statics.deribit.com/files/TermsofServiceDeribit.pdf",
        "attribution": "Deribit",
    },
    "internal": {
        "name": "Atlas Macro Derived Data",
        "homepage": "",
        "kind": "derived",
        "license_status": Source.LicenseStatus.OPEN,
        "license_scope": "Original calculations derived from attributed inputs",
        "redistribution_allowed": True,
        "public_display_allowed": True,
        "derived_display_allowed": True,
        "historical_storage_allowed": True,
        "ai_use_allowed": True,
        "attribution": "Atlas Macro",
    },
}


def ensure_source(key: str, **overrides: Any) -> Source:
    """Get or create a catalogued data source without replacing admin edits."""

    defaults = {**SOURCE_CATALOG.get(key, {"name": key.replace("-", " ").title()}), **overrides}
    source_field_names = {
        "name",
        "homepage",
        "kind",
        "license_status",
        "license_scope",
        "redistribution_allowed",
        "attribution",
    }
    source_defaults = {field: value for field, value in defaults.items() if field in source_field_names}
    source, created = Source.objects.get_or_create(key=key, defaults=source_defaults)
    # Correct unsafe seed defaults while preserving a later explicit licensed contract.
    if not created and source.license_status != Source.LicenseStatus.LICENSED:
        for field in (
            "name",
            "homepage",
            "kind",
            "license_status",
            "license_scope",
            "redistribution_allowed",
            "attribution",
        ):
            if field in source_defaults:
                setattr(source, field, source_defaults[field])
        source.save()
    if source.license_status == Source.LicenseStatus.LICENSED and source.licenses.filter(
        status=Source.LicenseStatus.LICENSED
    ).exists():
        return source
    licence_defaults = {
        "status": defaults.get("license_status", Source.LicenseStatus.REVIEW),
        "scope": defaults.get("license_scope", "Terms review required before publication"),
        "terms_url": defaults.get("terms_url", defaults.get("homepage", "")),
        "redistribution_allowed": defaults.get("redistribution_allowed", False),
        "public_display_allowed": defaults.get("public_display_allowed", False),
        "derived_display_allowed": defaults.get("derived_display_allowed", False),
        "historical_storage_allowed": defaults.get("historical_storage_allowed", False),
        "ai_use_allowed": defaults.get("ai_use_allowed", False),
        "territories": defaults.get("territories", "Worldwide public web"),
    }
    if not source.licenses.filter(**licence_defaults).exists():
        SourceLicense.objects.create(
            source=source,
            **licence_defaults,
            notes="Created automatically on first ingestion; review in Django Admin.",
        )
    return source


def begin_ingestion(
    source: Source | str, dataset: str, *, metadata: Mapping[str, Any] | None = None
) -> IngestionRun:
    source_obj = ensure_source(source) if isinstance(source, str) else source
    return IngestionRun.objects.create(
        source=source_obj,
        dataset=dataset[:120],
        started_at=timezone.now(),
        metadata=dict(metadata or {}),
    )


def finish_ingestion(
    run: IngestionRun,
    *,
    status: str,
    row_count: int = 0,
    error: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> IngestionRun:
    run.status = status
    run.row_count = max(0, int(row_count))
    run.error = error[:8000]
    run.completed_at = timezone.now()
    if metadata:
        run.metadata = {**run.metadata, **dict(metadata)}
    run.save(
        update_fields=["status", "row_count", "error", "completed_at", "metadata", "updated_at"]
    )
    check_status = {
        IngestionRun.Status.SUCCESS: QualityCheck.Status.PASS,
        IngestionRun.Status.PARTIAL: QualityCheck.Status.WARN,
        IngestionRun.Status.FAILED: QualityCheck.Status.FAIL,
    }.get(status, QualityCheck.Status.WARN)
    QualityCheck.objects.update_or_create(
        run=run,
        batch_id=run.batch_id,
        scope_key=f"{run.source.key}:{run.dataset}"[:160],
        check_name="provider_result",
        defaults={
            "status": check_status,
            "observed_at": run.completed_at,
            "details": {"row_count": run.row_count, "error": run.error},
        },
    )
    return run


def record_provider_result(
    result: ProviderResult,
    *,
    source_key: str | None = None,
    persist: Callable[[ProviderResult, Source, IngestionRun], int] | None = None,
) -> IngestionRun:
    """Persist a provider outcome and optionally normalize its records atomically."""

    key = source_key or result.provider
    run = begin_ingestion(
        key,
        result.dataset,
        metadata={"provider": result.provider, "fetched_at": result.fetched_at.isoformat()},
    )
    if result.skipped:
        return finish_ingestion(
            run,
            status=IngestionRun.Status.PARTIAL,
            metadata={**result.metadata, "skipped": True},
        )
    if result.error:
        return finish_ingestion(run, status=IngestionRun.Status.FAILED, error=result.error)

    try:
        with transaction.atomic():
            row_count = persist(result, run.source, run) if persist else result.row_count
    except Exception as exc:
        return finish_ingestion(
            run,
            status=IngestionRun.Status.FAILED,
            error=f"{type(exc).__name__}: {exc}",
        )
    return finish_ingestion(
        run,
        status=IngestionRun.Status.SUCCESS,
        row_count=row_count,
        metadata=result.metadata,
    )


def _aware_midnight(value: str | date | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    else:
        dt = parse_datetime(value) or datetime.combine(parse_date(value) or date.min, time.min)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, UTC)
    return dt


SERIES_CATALOG = {
    "SOFR": ("Secured Overnight Financing Rate", "%", "daily"),
    "EFFR": ("Effective Federal Funds Rate", "%", "daily"),
    "TGA": ("Treasury General Account Closing Balance", "USD millions", "daily"),
    "CES0000000001": ("Total Nonfarm Payroll Employment", "thousands", "monthly"),
    "LNS14000000": ("Unemployment Rate", "%", "monthly"),
    "CES0500000003": ("Average Hourly Earnings, Total Private", "USD/hour", "monthly"),
    "JTS000000000000000JOL": ("Job Openings", "thousands", "monthly"),
    "CUSR0000SA0": ("Consumer Price Index for All Urban Consumers", "index", "monthly"),
    "CUSR0000SA0L1E": ("Core CPI, All Items Less Food and Energy", "index", "monthly"),
    "WPSFD4": ("Producer Price Index: Final Demand", "index", "monthly"),
}


def store_series_observations(result: ProviderResult, source: Source, run: IngestionRun) -> int:
    """Upsert normalized observations from any official time-series provider."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in result.records:
        if record.get("series_id") and record.get("date") and record.get("value") is not None:
            grouped[str(record["series_id"])].append(record)
    now = timezone.now()
    count = 0
    for series_id, records in grouped.items():
        name, unit, frequency = SERIES_CATALOG.get(
            series_id,
            (
                series_id.replace("UST-", "U.S. Treasury ").replace("TIPS-", "Treasury Real "),
                "%" if series_id.startswith(("UST-", "TIPS-")) else "",
                "daily",
            ),
        )
        series, _ = SeriesDefinition.objects.get_or_create(
            key=series_id.lower(),
            defaults={
                "name": name,
                "unit": unit,
                "source": source,
                "frequency": frequency,
                "description": f"Imported directly from {source.name}.",
            },
        )
        for record in records:
            value_date = _aware_midnight(record["date"])
            metadata = dict(record.get("metadata") or {})
            for key in ("realtime_start", "realtime_end"):
                if record.get(key) is not None:
                    metadata[key] = record[key]
            Observation.objects.update_or_create(
                series=series,
                instrument=None,
                value_date=value_date,
                source=source,
                defaults={
                    "value": record["value"],
                    "as_of": value_date,
                    "fetched_at": now,
                    "batch_id": run.batch_id,
                    "quality_status": Observation.Quality.FRESH,
                    "metadata": metadata,
                },
            )
            count += 1
    return count


def store_fred_observations(result: ProviderResult, source: Source, run: IngestionRun) -> int:
    """Backward-compatible FRED normalizer."""

    return store_series_observations(result, source, run)


def store_market_observation(
    *,
    symbol: str,
    name: str,
    asset_class: str,
    value: Decimal | float | str,
    value_date: datetime,
    source: Source,
    run: IngestionRun,
    metadata: Mapping[str, Any] | None = None,
) -> Observation:
    instrument, _ = Instrument.objects.get_or_create(
        symbol=symbol,
        defaults={"name": name, "asset_class": asset_class},
    )
    if timezone.is_naive(value_date):
        value_date = timezone.make_aware(value_date, UTC)
    observation, _ = Observation.objects.update_or_create(
        instrument=instrument,
        series=None,
        value_date=value_date,
        source=source,
        defaults={
            "value": value,
            "as_of": value_date,
            "fetched_at": timezone.now(),
            "batch_id": run.batch_id,
            "quality_status": Observation.Quality.FRESH,
            "metadata": dict(metadata or {}),
        },
    )
    return observation


def store_okx_ticker(result: ProviderResult, source: Source, run: IngestionRun) -> int:
    count = 0
    for record in result.records:
        last = record.get("last")
        symbol = record.get("instId")
        if not symbol or _safe_decimal(last) is None:
            continue
        timestamp_ms = int(record.get("ts") or 0)
        value_date = (
            datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
            if timestamp_ms
            else result.fetched_at
        )
        store_market_observation(
            symbol=symbol,
            name=symbol.replace("-", " / "),
            asset_class="crypto",
            value=last,
            value_date=value_date,
            source=source,
            run=run,
            metadata={"bid": record.get("bidPx"), "ask": record.get("askPx")},
        )
        count += 1
    return count


def _safe_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except Exception:
        return None


def store_github_repository(result: ProviderResult, _: Source, __: IngestionRun) -> int:
    count = 0
    for record in result.records:
        pushed_at = parse_datetime(record.get("pushed_at") or "")
        GitHubProject.objects.update_or_create(
            repo=record["repo"],
            defaults={
                "category": (record.get("topics") or ["AI 应用"])[0],
                "description": record.get("description", ""),
                "stars": record.get("stars", 0),
                "forks": record.get("forks", 0),
                "open_issues": record.get("open_issues", 0),
                "pushed_at": pushed_at,
                "homepage": record.get("homepage") or f"https://github.com/{record['repo']}",
            },
        )
        count += 1
    return count


def store_cftc_positions(result: ProviderResult, source: Source, run: IngestionRun) -> int:
    count = 0
    for record in result.records:
        CFTCPosition.objects.update_or_create(
            report_type=record["report_type"],
            report_date=parse_date(record["report_date"]),
            market_code=record["market_code"],
            trader_group=record["trader_group"],
            defaults={
                "market_name": record["market_name"],
                "long_positions": record["long_positions"],
                "short_positions": record["short_positions"],
                "open_interest": record.get("open_interest"),
                "fetched_at": timezone.now(),
                "batch_id": run.batch_id,
                "source": source,
                "quality_status": Observation.Quality.FRESH,
            },
        )
        count += 1
    return count


def store_fed_documents(result: ProviderResult, _: Source, __: IngestionRun) -> int:
    count = 0
    for record in result.records:
        published_at = parse_datetime(record.get("published_at") or "")
        if not published_at:
            continue
        FedDocument.objects.update_or_create(
            slug=record["slug"],
            defaults={
                "document_type": record["document_type"],
                "title": record["title"],
                "speaker": "",
                "summary": record.get("summary", ""),
                "key_points": [],
                "published_at": published_at,
                "hawkish_score": 0,
                "original_url": record["original_url"],
            },
        )
        count += 1
    return count


def store_treasury_auctions(result: ProviderResult, source: Source, run: IngestionRun) -> int:
    count = 0
    for record in result.records:
        TreasuryAuction.objects.update_or_create(
            cusip=record["cusip"],
            auction_date=parse_date(record["auction_date"]),
            defaults={
                "security_type": record["security_type"],
                "security_term": record["security_term"],
                "announcement_date": parse_date(record.get("announcement_date") or ""),
                "issue_date": parse_date(record.get("issue_date") or ""),
                "maturity_date": parse_date(record.get("maturity_date") or ""),
                "offering_amount": record.get("offering_amt"),
                "total_tendered": record.get("total_tendered"),
                "total_accepted": record.get("total_accepted"),
                "bid_to_cover_ratio": record.get("bid_to_cover_ratio"),
                "high_yield": record.get("high_yield"),
                "indirect_bidder_accepted": record.get("indirect_bidder_accepted"),
                "direct_bidder_accepted": record.get("direct_bidder_accepted"),
                "primary_dealer_accepted": record.get("primary_dealer_accepted"),
                "fetched_at": timezone.now(),
                "batch_id": run.batch_id,
                "source": source,
                "quality_status": Observation.Quality.FRESH,
            },
        )
        count += 1
    return count


def store_raw_artifact(
    run: IngestionRun,
    *,
    uri: str,
    content: bytes,
    content_type: str = "application/json",
) -> RawArtifact:
    """Record the immutable metadata for an externally stored raw response."""

    return RawArtifact.objects.create(
        run=run,
        uri=uri,
        sha256=hashlib.sha256(content).hexdigest(),
        content_type=content_type,
        size_bytes=len(content),
    )


def latest_observation(
    *, series_key: str | None = None, instrument_symbol: str | None = None
) -> Observation | None:
    if bool(series_key) == bool(instrument_symbol):
        raise ValueError("provide exactly one of series_key or instrument_symbol")
    queryset = Observation.objects.select_related("source", "series", "instrument")
    if series_key:
        queryset = queryset.filter(series__key=series_key)
    else:
        queryset = queryset.filter(instrument__symbol=instrument_symbol)
    return queryset.order_by("-value_date").first()


def serialize_run(run: IngestionRun) -> dict[str, Any]:
    """Return a stable Celery-result representation."""

    return {
        "batch_id": str(run.batch_id),
        "source": run.source.key,
        "dataset": run.dataset,
        "status": run.status,
        "row_count": run.row_count,
        "error": run.error,
        "metadata": json.loads(json.dumps(run.metadata, default=str)),
    }


def summarize_runs(runs: Iterable[IngestionRun]) -> dict[str, Any]:
    rows = [serialize_run(run) for run in runs]
    return {
        "runs": rows,
        "row_count": sum(row["row_count"] for row in rows),
        "failed": sum(row["status"] == IngestionRun.Status.FAILED for row in rows),
        "partial": sum(row["status"] == IngestionRun.Status.PARTIAL for row in rows),
    }
