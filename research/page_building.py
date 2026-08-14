"""Shared public-page building and observation-reading primitives.

This is a deliberate import leaf: it may depend on models, services and the
standard library only.  Both ``official_data`` and the strict page contracts
import these helpers from here, which keeps the contract modules from
re-importing ``official_data`` (the historical module cycle) while preserving
one canonical implementation of freshness, licence-filtered reads and chart /
metric presentation contracts.
"""

from __future__ import annotations

import calendar
import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.utils import timezone

from .models import IngestionRun, Observation
from .services import public_display_license_q

FRESHNESS_DAYS = {
    "intraday": 1,
    "daily": 4,
    "weekly": 10,
    "monthly": 45,
    "quarterly": 120,
    "annual": 400,
}

ASSETS_FX_DATASET = ("federal-reserve", "h10")

def _fresh_until(observation: Observation) -> datetime:
    """Return a deadline from the observation period end, not period start."""

    value_date = observation.value_date
    frequency = observation.series.frequency
    release_date = (observation.metadata or {}).get("source_release_time") or (
        observation.metadata or {}
    ).get("source_revision_date")
    release_freshness_days = (observation.metadata or {}).get("release_freshness_days")
    if release_date and release_freshness_days:
        try:
            released_at = datetime.fromisoformat(str(release_date))
            if released_at.tzinfo is None:
                released_at = released_at.replace(tzinfo=UTC)
            release_deadline = released_at + timedelta(days=int(release_freshness_days))
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
    elif frequency == "daily":
        deadline_date = value_date.date() + timedelta(days=FRESHNESS_DAYS["daily"])
        return datetime.combine(
            deadline_date,
            time(hour=10),
            tzinfo=ZoneInfo("America/New_York"),
        ).astimezone(UTC)
    else:
        period_end = value_date
    return (
        period_end
        + timedelta(days=FRESHNESS_DAYS.get(frequency, 4) + 1)
        - timedelta(microseconds=1)
    )

def _real_observations(
    series_key: str,
    *,
    source_key: str | None = None,
    batch_id: uuid.UUID | str | None = None,
):
    queryset = (
        Observation.objects.filter(series__key=series_key.lower())
        .exclude(source__key="demo-market")
        .filter(public_display_license_q())
        .select_related("series", "source", "fallback_source")
        .distinct()
    )
    if source_key is not None:
        queryset = queryset.filter(source__key=source_key)
    if batch_id is not None:
        queryset = queryset.filter(batch_id=batch_id)
    return queryset.order_by("-value_date", "-fetched_at", "-id")

def _latest_observations_by_value_date(
    series_key: str,
    *,
    limit: int,
    source_key: str | None = None,
    batch_id: uuid.UUID | str | None = None,
) -> list[Observation]:
    """Return one deterministic latest-source observation per economic date."""

    observations: list[Observation] = []
    seen_dates = set()
    for observation in _real_observations(
        series_key, source_key=source_key, batch_id=batch_id
    ).iterator():
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
    aligned_with: Iterable[str] = (),
    source_key: str | None = None,
    batch_id: uuid.UUID | str | None = None,
    apply_freshness: bool = True,
) -> dict[str, Any] | None:
    alignment_keys = tuple(dict.fromkeys(aligned_with))
    if alignment_keys:
        observations_by_key = {
            key: {
                item.value_date.date(): item
                for item in _latest_observations_by_value_date(
                    key,
                    limit=2000,
                    source_key=source_key,
                    batch_id=batch_id,
                )
            }
            for key in (series_key, *alignment_keys)
        }
        common_dates = set.intersection(*(set(items) for items in observations_by_key.values()))
        today_et = timezone.now().astimezone(ZoneInfo("America/New_York")).date()
        periods = sorted(
            (period for period in common_dates if period <= today_et),
            reverse=True,
        )
        observations = [observations_by_key[series_key][period] for period in periods[:2]]
    else:
        observations = _latest_observations_by_value_date(
            series_key,
            limit=2,
            source_key=source_key,
            batch_id=batch_id,
        )
    if not observations:
        return None
    latest = observations[0]
    value = latest.value * scale
    previous = observations[1].value * scale if len(observations) > 1 else None
    change = value - previous if previous is not None else None
    fresh_until = _fresh_until(latest)
    quality_status = latest.quality_status
    if (
        apply_freshness
        and timezone.now() > fresh_until
        and quality_status == Observation.Quality.FRESH
    ):
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
        "fallback_source": (latest.fallback_source.key if latest.fallback_source_id else None),
        "as_of": latest.as_of.isoformat(),
        "value_date": latest.value_date.isoformat(),
        "fetched_at": latest.fetched_at.isoformat(),
        "fresh_until": fresh_until.isoformat(),
        "batch_id": str(latest.batch_id),
        "metadata": {
            **latest.metadata,
            **(
                {
                    "common_effective_date": latest.value_date.date().isoformat(),
                    "aligned_with": [key.lower() for key in alignment_keys],
                }
                if alignment_keys
                else {}
            ),
        },
    }

def _history_rows(
    series: dict[str, str],
    *,
    limit: int = 120,
    require_all: bool = False,
    source_key: str | None = None,
    batch_id: uuid.UUID | str | None = None,
) -> list[dict[str, Any]]:
    """Align public observations by date while preserving semantic series labels."""

    by_date: dict[str, dict[str, Any]] = {}
    for series_key, label in series.items():
        observations = _latest_observations_by_value_date(
            series_key,
            limit=limit,
            source_key=source_key,
            batch_id=batch_id,
        )
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
            row["_source_keys"] = sorted({*row["_source_keys"], *source_keys})
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
    rows = [by_date[day] for day in sorted(by_date)]
    if require_all:
        required_labels = set(series.values())
        today_et = timezone.now().astimezone(ZoneInfo("America/New_York")).date()
        rows = [
            row
            for row in rows
            if required_labels <= set(row) and date.fromisoformat(row["date"]) <= today_et
        ]
    return rows

def _history_chart(
    *,
    key: str,
    title: str,
    series: dict[str, str],
    limit: int = 120,
    description: str = "",
    kind: str = "line",
    source_key: str | None = None,
    batch_id: uuid.UUID | str | None = None,
    apply_freshness: bool = True,
) -> dict[str, Any] | None:
    """Build a chart contract with component-level source and freshness metadata."""

    rows = _history_rows(
        series,
        limit=limit,
        source_key=source_key,
        batch_id=batch_id,
    )
    if not rows:
        return None
    latest = [
        observation
        for series_key in series
        if (
            observation := _real_observations(
                series_key, source_key=source_key, batch_id=batch_id
            ).first()
        )
        is not None
    ]
    if len(latest) != len(series):
        return None
    deadlines = [_fresh_until(observation) for observation in latest]
    quality_statuses = {observation.quality_status for observation in latest}
    if Observation.Quality.ERROR in quality_statuses:
        quality_status = Observation.Quality.ERROR
    elif (
        apply_freshness and timezone.now() > min(deadlines)
    ) or Observation.Quality.STALE in quality_statuses:
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
        "frequency": (
            latest[0].series.frequency
            if len({observation.series.frequency for observation in latest}) == 1
            else ""
        ),
    }

def _latest_h10_attempt(*, lock: bool = False) -> IngestionRun | None:
    queryset = IngestionRun.objects.filter(
        source__key=ASSETS_FX_DATASET[0],
        dataset=ASSETS_FX_DATASET[1],
    ).select_related("source")
    if lock:
        queryset = queryset.select_for_update()
    return queryset.order_by("-started_at", "-id").first()

def _bind_calculated_record_lineage(result, source, run) -> None:
    """Attach the exact acquisition batch to first-party derived records."""

    for record in result.records:
        metadata = dict(record.get("metadata") or {})
        if metadata.get("calculation_owner") != "Atlas Macro":
            continue
        input_dates = list(metadata.get("input_value_dates") or [])
        input_values = list(metadata.get("input_values") or [])
        metadata["input_batch_ids"] = [str(run.batch_id)]
        input_series = list(metadata.get("input_series") or [])
        metadata["input_lineage"] = [
            {
                "series_key": str(input_series[0]).lower() if input_series else "",
                "source_key": source.key,
                "source_name": source.name,
                "value_date": str(value_date),
                "value": str(value),
                "fetched_at": result.fetched_at.isoformat(),
                "batch_id": str(run.batch_id),
                "quality_status": Observation.Quality.FRESH,
                "license_scope": source.license_scope,
                "fallback_source": None,
            }
            for value_date, value in zip(input_dates, input_values, strict=False)
        ]
        record["metadata"] = metadata
