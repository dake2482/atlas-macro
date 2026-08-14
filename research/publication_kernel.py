"""Shared append-only publication retention primitives.

The strict page contracts (GDP, employment, inflation, consumer, economy) each
retain the last complete replayable revision when a completed input set cannot
become the current public revision.  The marker write, the replayable-candidate
scan and the retained-state verification are structurally identical across
those domains; only the page key, contract version and replay hooks differ.

This module owns that shared machinery so the per-domain contracts stay thin
and cross-domain drift is impossible.  Each contract keeps its own
transaction/lock orchestration: the kernel primitives are deliberately free of
locking policy.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from typing import Any

from .models import DashboardSnapshot, Observation


def mark_retained_failure(
    snapshot: DashboardSnapshot,
    *,
    reason_code: str,
    reason: str,
    checked_at: datetime,
    marker_payload: dict[str, Any],
) -> None:
    """Annotate ``snapshot`` with a refresh-failure marker and turn it stale.

    ``marker_payload`` carries the domain-specific witnesses (``attempt``,
    ``attempts`` or ``components``) appended after the shared keys, matching the
    historical on-disk marker layout byte for byte.
    """

    data = deepcopy(snapshot.data or {})
    data["refresh_failure"] = {
        "reason_code": reason_code,
        "checked_at": checked_at.isoformat(),
        "reason": reason,
        **marker_payload,
    }
    snapshot.data = data
    snapshot.quality_status = Observation.Quality.STALE
    snapshot.save(update_fields=["data", "quality_status", "updated_at"])


def find_retainable_revision(
    *,
    page_key: str,
    contract_version: str,
    is_failed_target: Callable[[DashboardSnapshot], bool],
    static_replay: Callable[[DashboardSnapshot], Any],
    best_effort_replay: bool = True,
) -> DashboardSnapshot | None:
    """Return the newest replayable revision that is not the failed target.

    Callers must already hold the row locks their contract requires; the scan
    itself locks candidates with ``select_for_update(of=("self",))`` exactly as
    the historical per-domain scans did.  With ``best_effort_replay`` a
    candidate whose static replay raises is skipped (retention must never mask
    the original publication failure); otherwise the replay error propagates.
    """

    candidates = (
        DashboardSnapshot.objects.select_for_update(of=("self",))
        .filter(
            key=page_key,
            is_published=True,
            data__contract_version=contract_version,
        )
        .exclude(source__key="demo-market")
        .select_related("source")
        .order_by("-created_at", "-id")
    )
    for candidate in candidates:
        if is_failed_target(candidate):
            continue
        try:
            replay = static_replay(candidate)
        except Exception:
            if best_effort_replay:
                continue
            raise
        if replay is not None:
            return candidate
    return None


def verify_retained_state(
    *,
    selector: Callable[[], Any],
    state_attr: str,
    domain_label: str,
) -> None:
    """Fail loudly when the retained-failure marker is not publicly selected."""

    selected = selector()
    if selected is None or getattr(selected, state_attr, None) != "retained_failure":
        raise ValueError(
            f"{domain_label} publication-postcondition marker did not replay"
        )
