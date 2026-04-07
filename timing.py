"""
Timing derivation — extracts lead time, cycle time, and backlog wait
from changelog transitions.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from models import Phase, StatusTransition, Confidence


@dataclass
class TimingResult:
    started_at: Optional[datetime]
    resolved_at: Optional[datetime]
    lead_time_days: Optional[float]
    cycle_time_days: Optional[float]
    backlog_wait_days: Optional[float]
    has_rework_transition: bool  # moved backward from done/review to active/ready
    has_rework_status: bool      # changelog contains a configured rework status
    confidence: Confidence


def _days_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 86400


def derive_timing(
    created_at: datetime,
    changelog: List[StatusTransition],
    resolved_static: Optional[datetime] = None,
    rework_statuses: Optional[List[str]] = None,
) -> TimingResult:
    """Derive timing metrics from changelog transitions.

    Uses first transition into active/review as started_at,
    and first transition into done as resolved_at.
    Falls back to static resolved date if changelog is empty.

    Args:
        rework_statuses: Optional list of status names that indicate rework
            (e.g. ["reopened", "rework"]). If a changelog transition targets
            one of these statuses, has_rework_status is set to True.
    """
    rework_set = {s.lower() for s in (rework_statuses or [])}

    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    has_rework = False
    has_rework_status = False

    # Track whether we've seen done/review before to detect rework
    seen_done = False
    seen_review = False

    for transition in sorted(changelog, key=lambda t: t.timestamp):
        to_phase = transition.to_phase

        # First transition into active or review = started
        if started_at is None and to_phase in (Phase.ACTIVE, Phase.REVIEW):
            started_at = transition.timestamp

        # First transition into done = resolved
        if resolved_at is None and to_phase == Phase.DONE:
            resolved_at = transition.timestamp

        # Rework detection: backward movement from done/review
        if seen_done and to_phase in (Phase.ACTIVE, Phase.READY):
            has_rework = True
        if seen_review and to_phase in (Phase.ACTIVE, Phase.READY, Phase.BACKLOG):
            has_rework = True

        # Rework detection: configured rework status names
        if transition.to_status.lower() in rework_set:
            has_rework_status = True

        if to_phase == Phase.DONE:
            seen_done = True
        if to_phase == Phase.REVIEW:
            seen_review = True

    # Determine confidence
    if changelog and started_at and resolved_at:
        confidence = Confidence.HIGH
    elif changelog and resolved_at:
        # Have changelog but couldn't determine start — use resolved only
        confidence = Confidence.MEDIUM
    elif resolved_static:
        # No changelog, fall back to static field
        resolved_at = resolved_static
        confidence = Confidence.LOW
    else:
        confidence = Confidence.LOW

    # Compute durations
    lead_time = None
    cycle_time = None
    backlog_wait = None

    if resolved_at is not None:
        lead_time = _days_between(created_at, resolved_at)

    if started_at is not None and resolved_at is not None:
        cycle_time = _days_between(started_at, resolved_at)

    if started_at is not None:
        backlog_wait = _days_between(created_at, started_at)

    return TimingResult(
        started_at=started_at,
        resolved_at=resolved_at,
        lead_time_days=round(lead_time, 2) if lead_time is not None else None,
        cycle_time_days=round(cycle_time, 2) if cycle_time is not None else None,
        backlog_wait_days=round(backlog_wait, 2) if backlog_wait is not None else None,
        has_rework_transition=has_rework,
        has_rework_status=has_rework_status,
        confidence=confidence,
    )
