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
    )
