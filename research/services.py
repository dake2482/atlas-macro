"""Application services for lineage-aware ingestion and data access."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import (
    GitHubProject,
    IngestionRun,
    Instrument,
    Observation,
    RawArtifact,
    SeriesDefinition,
    Source,
    SourceLicense,
)
from .providers import ProviderResult

SOURCE_CATALOG: dict[str, dict[str, Any]] = {
    "fred": {
        "name": "Federal Reserve Economic Data",
        "homepage": "https://fred.stlouisfed.org/",
        "kind": "official",
        "license_status": Source.LicenseStatus.OPEN,
        "license_scope": "FRED terms and source-series attribution apply",
        "redistribution_allowed": True,
        "attribution": "Federal Reserve Bank of St. Louis",
    },
    "sec": {
        "name": "SEC EDGAR",
        "homepage": "https://www.sec.gov/edgar",
        "kind": "official",
        "license_status": Source.LicenseStatus.OPEN,
        "license_scope": "Public filings; issuer material retains its own rights",
        "redistribution_allowed": True,
        "attribution": "U.S. Securities and Exchange Commission",
    },
    "github": {
        "name": "GitHub REST API",
        "homepage": "https://docs.github.com/en/rest",
        "kind": "public-api",
        "license_status": Source.LicenseStatus.REVIEW,
        "license_scope": "Metadata only; repository licenses apply separately",
        "redistribution_allowed": False,
        "attribution": "GitHub",
    },
    "okx": {
        "name": "OKX Public Market Data",
        "homepage": "https://www.okx.com/docs-v5/",
        "kind": "public-api",
        "license_status": Source.LicenseStatus.REVIEW,
        "license_scope": "Public delayed display; review production redistribution",
        "redistribution_allowed": False,
        "attribution": "OKX",
    },
    "deribit": {
        "name": "Deribit Public API",
        "homepage": "https://docs.deribit.com/",
        "kind": "public-api",
        "license_status": Source.LicenseStatus.REVIEW,
        "license_scope": "Public delayed display; review production redistribution",
        "redistribution_allowed": False,
        "attribution": "Deribit",
    },
    "internal": {
        "name": "Atlas Macro Derived Data",
        "homepage": "",
        "kind": "derived",
        "license_status": Source.LicenseStatus.OPEN,
        "license_scope": "Original calculations derived from attributed inputs",
        "redistribution_allowed": True,
        "attribution": "Atlas Macro",
    },
}


def ensure_source(key: str, **overrides: Any) -> Source:
    """Get or create a catalogued data source without replacing admin edits."""

    defaults = {**SOURCE_CATALOG.get(key, {"name": key.replace("-", " ").title()}), **overrides}
    source, _ = Source.objects.get_or_create(key=key, defaults=defaults)
    if not source.licenses.exists():
        SourceLicense.objects.create(
            source=source,
            status=defaults.get("license_status", Source.LicenseStatus.REVIEW),
            scope=defaults.get("license_scope", "Terms review required before publication"),
            terms_url=defaults.get("homepage", ""),
            redistribution_allowed=defaults.get("redistribution_allowed", False),
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


def store_fred_observations(result: ProviderResult, source: Source, run: IngestionRun) -> int:
    """Upsert normalized FRED observations using the ingestion batch id."""

    if not result.records:
        return 0
    series_id = str(result.records[0]["series_id"])
    series, _ = SeriesDefinition.objects.get_or_create(
        key=series_id.lower(),
        defaults={
            "name": series_id,
            "source": source,
            "frequency": "daily",
            "description": "Imported from FRED; metadata can be curated in admin.",
        },
    )
    now = timezone.now()
    count = 0
    for record in result.records:
        value_date = _aware_midnight(record["date"])
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
                "metadata": {
                    "realtime_start": record.get("realtime_start"),
                    "realtime_end": record.get("realtime_end"),
                },
            },
        )
        count += 1
    return count


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
