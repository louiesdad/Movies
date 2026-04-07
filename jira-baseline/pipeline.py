"""
Pipeline — orchestrates the full analysis flow from raw issues to normalized
tickets, bucket metrics, and exports.
"""

from datetime import datetime
from typing import List, Optional

from models import (
    JiraIssue, NormalizedTicket, BucketMetrics, AnalysisSummary,
    NormalizedType, Size, Area, Confidence, Outcome,
    ExclusionReason, Phase,
)
from config import ProjectConfig
from normalizer import StatusNormalizer, normalize_type, is_epic_type
from timing import derive_timing
from classifier import classify_size, classify_area
from metrics import compute_bucket_metrics, build_summary


def normalize_issue(
    issue: JiraIssue,
    status_normalizer: StatusNormalizer,
    config: ProjectConfig,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
) -> NormalizedTicket:
    """Transform a raw JiraIssue into a NormalizedTicket."""

    # Type
    norm_type = normalize_type(issue.issue_type)
    is_epic = is_epic_type(issue.issue_type)

    # Status
    status_mapping = status_normalizer.map(issue.status)
    status_confidence = Confidence.HIGH if status_mapping.confidence >= 0.8 else (
        Confidence.MEDIUM if status_mapping.confidence >= 0.6 else Confidence.LOW
    )

    # Duplicate — check both resolution field AND status mapped as duplicate
    is_duplicate = (
        status_normalizer.is_duplicate_resolution(issue.resolution)
        or status_normalizer.is_duplicate_status(issue.status)
    )

    # Timing (pass config rework_statuses for status-name-based rework detection)
    timing = derive_timing(
        created_at=issue.created,
        changelog=issue.changelog,
        resolved_static=issue.resolved,
        rework_statuses=config.rework_statuses,
    )

    # Size
    size, size_confidence = classify_size(
        story_points=issue.story_points,
        description=issue.description,
        acceptance_criteria=issue.acceptance_criteria,
        subtasks=issue.subtasks,
        dependencies=issue.dependencies,
    )

    # Area
    area, area_confidence = classify_area(
        components=issue.components,
        labels=issue.labels,
        summary=issue.summary,
        config=config,
    )

    # Bug detection — two sources:
    #   1. Pre-filtered linked_bugs from Jira client
    #   2. issue_links matched against config.defect_link_types
    defect_types = {t.lower() for t in config.defect_link_types}
    has_bug_from_links = any(
        isinstance(link, dict) and link.get("type", "").lower() in defect_types
        for link in (issue.issue_links or [])
    )
    has_bug = len(issue.linked_bugs) > 0 or has_bug_from_links

    # Rework detection — independent from bug detection.
    # A linked bug means a defect was found, NOT that rework occurred.
    # Rework signals come only from the changelog:
    #   1. Backward transition (done/review → active/ready) — high confidence
    #   2. Configured rework status appeared in changelog — high confidence
    has_rework = timing.has_rework_transition or timing.has_rework_status
    rework_confidence = None
    if has_rework:
        rework_confidence = Confidence.HIGH

    # Exclusion logic
    included = True
    exclusion_reason = None

    if is_epic:
        included = False
        exclusion_reason = ExclusionReason.EPIC
    elif is_duplicate:
        included = False
        exclusion_reason = ExclusionReason.DUPLICATE
    elif timing.resolved_at is None:
        included = False
        exclusion_reason = ExclusionReason.UNRESOLVED
    elif timing.cycle_time_days is None and timing.lead_time_days is None:
        included = False
        exclusion_reason = ExclusionReason.MISSING_TIMING
    elif window_start and issue.created < window_start:
        included = False
        exclusion_reason = ExclusionReason.OUTSIDE_WINDOW
    elif window_end and issue.created > window_end:
        included = False
        exclusion_reason = ExclusionReason.OUTSIDE_WINDOW

    # Outcome (precedence: bug > rework > clean > incomplete)
    if not included or timing.resolved_at is None:
        outcome = Outcome.INCOMPLETE
    elif has_bug:
        outcome = Outcome.COMPLETED_WITH_BUG
    elif has_rework:
        outcome = Outcome.COMPLETED_WITH_REWORK
    else:
        outcome = Outcome.COMPLETED_CLEAN

    return NormalizedTicket(
        key=issue.key,
        project=issue.project,
        normalized_type=norm_type,
        size=size,
        size_confidence=size_confidence,
        area=area,
        area_confidence=area_confidence,
        created_at=issue.created,
        started_at=timing.started_at,
        resolved_at=timing.resolved_at,
        lead_time_days=timing.lead_time_days,
        cycle_time_days=timing.cycle_time_days,
        backlog_wait_days=timing.backlog_wait_days,
        has_bug=has_bug,
        has_rework=has_rework,
        rework_confidence=rework_confidence,
        is_duplicate=is_duplicate,
        is_epic=is_epic,
        status_mapping_confidence=status_confidence,
        included_in_baseline=included,
        exclusion_reason=exclusion_reason,
        outcome=outcome,
        raw_summary=issue.summary,
        raw_type=issue.issue_type,
        raw_status=issue.status,
    )


def run_analysis(
    issues: List[JiraIssue],
    project_key: str,
    config: Optional[ProjectConfig] = None,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
) -> tuple:
    """Run full analysis pipeline.

    Returns (tickets, bucket_metrics, summary).
    """
    cfg = config or ProjectConfig()
    normalizer = StatusNormalizer(
        overrides=cfg.status_overrides,
        extra_done_statuses=cfg.done_statuses,
    )

    # Surface any invalid override warnings
    if normalizer._invalid_overrides:
        import sys
        for warning in normalizer._invalid_overrides:
            print(f"WARNING: invalid status override {warning}", file=sys.stderr)

    # Normalize all issues
    tickets = [
        normalize_issue(issue, normalizer, cfg, window_start, window_end)
        for issue in issues
    ]

    # Compute bucket metrics
    bucket_metrics = compute_bucket_metrics(tickets)

    # Build summary
    summary = build_summary(
        project_key=project_key,
        tickets=tickets,
        bucket_metrics=bucket_metrics,
        window_start=window_start,
        window_end=window_end,
    )

    return tickets, bucket_metrics, summary
