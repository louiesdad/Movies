"""
Export — writes analysis results to JSON/JSONL/CSV files.
"""

import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional

from models import (
    NormalizedTicket, BucketMetrics, AnalysisSummary,
    BucketKey, Confidence, NormalizedType, Size, Area,
    Outcome, ExclusionReason, Phase,
)


def _serialize(obj):
    """JSON serializer for dataclass enums and datetimes."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (NormalizedType, Size, Area, Confidence,
                         Outcome, ExclusionReason, Phase)):
        return obj.value
    if isinstance(obj, BucketKey):
        return {"type": obj.type.value, "size": obj.size.value,
                "area": obj.area.value}
    raise TypeError(f"Cannot serialize {type(obj)}")


def _ticket_to_dict(t: NormalizedTicket) -> dict:
    """Convert a NormalizedTicket to a serializable dict."""
    return {
        "key": t.key,
        "project": t.project,
        "normalized_type": t.normalized_type.value,
        "size": t.size.value,
        "size_confidence": t.size_confidence.value,
        "area": t.area.value,
        "area_confidence": t.area_confidence.value,
        "created_at": t.created_at.isoformat(),
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
        "lead_time_days": t.lead_time_days,
        "cycle_time_days": t.cycle_time_days,
        "backlog_wait_days": t.backlog_wait_days,
        "has_bug": t.has_bug,
        "has_rework": t.has_rework,
        "rework_confidence": t.rework_confidence.value if t.rework_confidence else None,
        "is_duplicate": t.is_duplicate,
        "is_epic": t.is_epic,
        "status_mapping_confidence": t.status_mapping_confidence.value,
        "included_in_baseline": t.included_in_baseline,
        "exclusion_reason": t.exclusion_reason.value if t.exclusion_reason else None,
        "outcome": t.outcome.value,
        "raw_summary": t.raw_summary,
        "raw_type": t.raw_type,
        "raw_status": t.raw_status,
    }


def _bucket_to_dict(b: BucketMetrics) -> dict:
    return {
        "bucket": {
            "type": b.bucket.type.value,
            "size": b.bucket.size.value,
            "area": b.bucket.area.value,
        },
        "sample_size": b.sample_size,
        "median_cycle_time_days": b.median_cycle_time_days,
        "p75_cycle_time_days": b.p75_cycle_time_days,
        "median_lead_time_days": b.median_lead_time_days,
        "median_backlog_wait_days": b.median_backlog_wait_days,
        "bug_rate": b.bug_rate,
        "rework_rate": b.rework_rate,
        "clean_completion_rate": b.clean_completion_rate,
        "baseline_confidence": b.baseline_confidence.value,
    }


def _summary_to_dict(s: AnalysisSummary) -> dict:
    return {
        "project_key": s.project_key,
        "analysis_window_start": s.analysis_window_start.isoformat() if s.analysis_window_start else None,
        "analysis_window_end": s.analysis_window_end.isoformat() if s.analysis_window_end else None,
        "total_issues_fetched": s.total_issues_fetched,
        "total_included_in_baseline": s.total_included_in_baseline,
        "total_excluded": s.total_excluded,
        "exclusion_breakdown": s.exclusion_breakdown,
        "bucket_count": s.bucket_count,
        "high_confidence_buckets": s.high_confidence_buckets,
        "slow_buckets": [_bucket_to_dict(b) for b in s.slow_buckets],
        "quality_hotspots": [_bucket_to_dict(b) for b in s.quality_hotspots],
    }


def export_tickets_jsonl(tickets: List[NormalizedTicket], path: str):
    """Write normalized tickets as JSONL (one JSON object per line)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        for t in tickets:
            f.write(json.dumps(_ticket_to_dict(t)) + "\n")


def export_buckets_json(buckets: List[BucketMetrics], path: str):
    """Write bucket baselines as JSON array."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump([_bucket_to_dict(b) for b in buckets], f, indent=2)


def export_summary_json(summary: AnalysisSummary, path: str):
    """Write analysis summary as JSON."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(_summary_to_dict(summary), f, indent=2)


def export_buckets_csv(buckets: List[BucketMetrics], path: str):
    """Write bucket baselines as CSV."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    headers = [
        "type", "size", "area", "sample_size",
        "median_cycle_time_days", "p75_cycle_time_days",
        "median_lead_time_days", "median_backlog_wait_days",
        "bug_rate", "rework_rate", "clean_completion_rate",
        "baseline_confidence",
    ]
    with open(path, "w") as f:
        f.write(",".join(headers) + "\n")
        for b in buckets:
            row = [
                b.bucket.type.value, b.bucket.size.value, b.bucket.area.value,
                str(b.sample_size),
                str(b.median_cycle_time_days or ""),
                str(b.p75_cycle_time_days or ""),
                str(b.median_lead_time_days or ""),
                str(b.median_backlog_wait_days or ""),
                str(b.bug_rate), str(b.rework_rate),
                str(b.clean_completion_rate),
                b.baseline_confidence.value,
            ]
            f.write(",".join(row) + "\n")
