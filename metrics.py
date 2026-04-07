"""
Metrics aggregation — computes per-bucket baseline statistics.
"""

import statistics
from typing import Dict, List, Optional

from models import (
    NormalizedTicket, BucketKey, BucketMetrics, Confidence,
    AnalysisSummary, Outcome, ExclusionReason,
)
from datetime import datetime


def _percentile(data: List[float], pct: float) -> float:
    """Compute a percentile from sorted data."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (pct / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def compute_bucket_metrics(tickets: List[NormalizedTicket]) -> List[BucketMetrics]:
    """Group baseline-included tickets into buckets and compute metrics."""
    # Filter to baseline-included tickets only
    included = [t for t in tickets if t.included_in_baseline]

    # Group by bucket key
    buckets: Dict[BucketKey, List[NormalizedTicket]] = {}
    for t in included:
        key = BucketKey(type=t.normalized_type, size=t.size, area=t.area)
        buckets.setdefault(key, []).append(t)

    results: List[BucketMetrics] = []
    for bucket_key, group in sorted(buckets.items(), key=lambda x: str(x[0])):
        n = len(group)

        cycle_times = [t.cycle_time_days for t in group
                       if t.cycle_time_days is not None]
        lead_times = [t.lead_time_days for t in group
                      if t.lead_time_days is not None]
        backlog_waits = [t.backlog_wait_days for t in group
                         if t.backlog_wait_days is not None]

        bug_count = sum(1 for t in group if t.has_bug)
        rework_count = sum(1 for t in group if t.has_rework)
        clean_count = sum(1 for t in group
                          if t.outcome == Outcome.COMPLETED_CLEAN)

        # Confidence — factors: sample size, timing data quality,
        # and status mapping confidence across the bucket
        timing_ratio = len(cycle_times) / n if n > 0 else 0
        high_conf_status = sum(
            1 for t in group
            if t.status_mapping_confidence == Confidence.HIGH
        )
        status_quality = high_conf_status / n if n > 0 else 0

        if n >= 20 and timing_ratio >= 0.7 and status_quality >= 0.5:
            confidence = Confidence.HIGH
        elif n >= 8 and timing_ratio >= 0.5:
            confidence = Confidence.MEDIUM
        elif n >= 5 and timing_ratio >= 0.5:
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.LOW

        results.append(BucketMetrics(
            bucket=bucket_key,
            sample_size=n,
            median_cycle_time_days=(
                round(statistics.median(cycle_times), 1) if cycle_times else None
            ),
            p75_cycle_time_days=(
                round(_percentile(cycle_times, 75), 1) if cycle_times else None
            ),
            median_lead_time_days=(
                round(statistics.median(lead_times), 1) if lead_times else None
            ),
            median_backlog_wait_days=(
                round(statistics.median(backlog_waits), 1) if backlog_waits else None
            ),
            bug_rate=round(bug_count / n, 3) if n > 0 else 0,
            rework_rate=round(rework_count / n, 3) if n > 0 else 0,
            clean_completion_rate=round(clean_count / n, 3) if n > 0 else 0,
            baseline_confidence=confidence,
        ))

    return results


def build_summary(
    project_key: str,
    tickets: List[NormalizedTicket],
    bucket_metrics: List[BucketMetrics],
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
) -> AnalysisSummary:
    """Build a summary report from normalized tickets and bucket metrics."""
    included = [t for t in tickets if t.included_in_baseline]
    excluded = [t for t in tickets if not t.included_in_baseline]

    # Exclusion breakdown
    exclusion_breakdown: Dict[str, int] = {}
    for t in excluded:
        reason = t.exclusion_reason.value if t.exclusion_reason else "unknown"
        exclusion_breakdown[reason] = exclusion_breakdown.get(reason, 0) + 1

    high_conf = sum(1 for b in bucket_metrics
                    if b.baseline_confidence == Confidence.HIGH)

    # Top 5 slow buckets (by median cycle time, descending)
    with_cycle = [b for b in bucket_metrics
                  if b.median_cycle_time_days is not None]
    slow = sorted(with_cycle,
                  key=lambda b: b.median_cycle_time_days, reverse=True)[:5]

    # Top 5 quality hotspots (by combined bug+rework rate)
    quality = sorted(bucket_metrics,
                     key=lambda b: b.bug_rate + b.rework_rate,
                     reverse=True)[:5]

    # Data quality overview
    total_with_timing = sum(1 for t in included
                            if t.cycle_time_days is not None)
    total_high_status = sum(1 for t in included
                            if t.status_mapping_confidence == Confidence.HIGH)
    total_high_size = sum(1 for t in included
                          if t.size_confidence == Confidence.HIGH)
    n_included = len(included) or 1  # avoid division by zero

    data_quality = {
        "timing_coverage": round(total_with_timing / n_included, 2),
        "status_mapping_quality": round(total_high_status / n_included, 2),
        "size_confidence_quality": round(total_high_size / n_included, 2),
        "included_ratio": round(len(included) / max(len(tickets), 1), 2),
    }

    # Generate actionable recommendations
    recommendations = _generate_recommendations(
        included, excluded, bucket_metrics, data_quality, high_conf)

    return AnalysisSummary(
        project_key=project_key,
        analysis_window_start=window_start,
        analysis_window_end=window_end,
        total_issues_fetched=len(tickets),
        total_included_in_baseline=len(included),
        total_excluded=len(excluded),
        exclusion_breakdown=exclusion_breakdown,
        bucket_count=len(bucket_metrics),
        high_confidence_buckets=high_conf,
        slow_buckets=slow,
        quality_hotspots=quality,
        data_quality=data_quality,
        recommendations=recommendations,
    )


def _generate_recommendations(
    included: List[NormalizedTicket],
    excluded: List[NormalizedTicket],
    buckets: List[BucketMetrics],
    data_quality: dict,
    high_conf_count: int,
) -> List[str]:
    """Generate actionable recommendations based on analysis results."""
    recs: List[str] = []

    # Data quality
    if data_quality["timing_coverage"] < 0.5:
        recs.append(
            "Low timing coverage: less than 50% of baseline tickets have "
            "cycle time data. Check that your Jira workflow has clear "
            "status transitions, or add status_overrides in config."
        )
    if data_quality["status_mapping_quality"] < 0.5:
        recs.append(
            "Many statuses mapped with low confidence. Review your "
            "workflow's custom statuses and add status_overrides for "
            "any that were not auto-detected."
        )
    if data_quality["size_confidence_quality"] < 0.5:
        recs.append(
            "Most tickets lack story points, causing low-confidence "
            "size classification. Consider adding story points to "
            "your workflow, or accept that size buckets will rely "
            "on content heuristics."
        )

    # Exclusion rate
    total = len(included) + len(excluded)
    if total > 0 and len(excluded) / total > 0.4:
        recs.append(
            f"High exclusion rate: {len(excluded)}/{total} tickets excluded. "
            "Check for unresolved tickets, duplicates, or Epics that "
            "dominate the project. Consider narrowing the analysis window."
        )

    # Bucket confidence
    if high_conf_count == 0 and len(buckets) > 0:
        recs.append(
            "No high-confidence buckets. The project may not have enough "
            "completed tickets per type/size/area combination. Consider "
            "broadening the analysis window or accepting medium-confidence "
            "baselines for comparison."
        )

    # Slow buckets
    slow = [b for b in buckets if b.median_cycle_time_days is not None
            and b.median_cycle_time_days > 14]
    if slow:
        names = ", ".join(str(b.bucket) for b in slow[:3])
        recs.append(
            f"Buckets with >14-day median cycle time: {names}. "
            "These are candidates for process improvement or "
            "scope reduction before AI comparison."
        )

    # Quality hotspots
    bad_quality = [b for b in buckets if b.bug_rate + b.rework_rate > 0.5]
    if bad_quality:
        names = ", ".join(str(b.bucket) for b in bad_quality[:3])
        recs.append(
            f"Buckets with >50% combined bug+rework rate: {names}. "
            "Investigate root causes before using these baselines "
            "for AI comparison."
        )

    if not recs:
        recs.append(
            "Data quality looks good. Baselines are ready for comparison."
        )

    return recs
