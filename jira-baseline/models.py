"""
Data models for the Jira Baseline Analytics system.

Defines the normalized ticket record, bucket metrics, and all enums
used throughout the pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NormalizedType(Enum):
    BUG = "bug"
    TASK = "task"
    STORY = "story"
    SPIKE = "spike"
    OTHER = "other"


class Size(Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    UNKNOWN = "unknown"


class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Area(Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    INFRA = "infra"
    MOBILE = "mobile"
    DATA = "data"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class Outcome(Enum):
    COMPLETED_WITH_BUG = "completed_with_bug"
    COMPLETED_WITH_REWORK = "completed_with_rework"
    COMPLETED_CLEAN = "completed_clean"
    INCOMPLETE = "incomplete"


class Phase(Enum):
    BACKLOG = "backlog"
    READY = "ready"
    ACTIVE = "active"
    REVIEW = "review"
    DONE = "done"
    UNKNOWN = "unknown"


class ExclusionReason(Enum):
    EPIC = "epic"
    DUPLICATE = "duplicate"
    UNRESOLVED = "unresolved"
    MISSING_TIMING = "missing_timing"
    INVALID_TYPE = "invalid_type"
    OUTSIDE_WINDOW = "outside_window"


# ---------------------------------------------------------------------------
# Status mapping result
# ---------------------------------------------------------------------------

@dataclass
class StatusMapping:
    raw_status: str
    phase: Phase
    confidence: float
    is_blocked: bool
    matched_keyword: str


# ---------------------------------------------------------------------------
# Changelog transition
# ---------------------------------------------------------------------------

@dataclass
class StatusTransition:
    timestamp: datetime
    from_status: str
    to_status: str
    from_phase: Phase
    to_phase: Phase


# ---------------------------------------------------------------------------
# Raw Jira issue (input from client)
# ---------------------------------------------------------------------------

@dataclass
class JiraIssue:
    key: str
    project: str
    issue_type: str
    status: str
    resolution: Optional[str]
    priority: Optional[str]
    summary: str
    description: str
    story_points: Optional[float]
    components: List[str]
    labels: List[str]
    acceptance_criteria: List[str]
    subtasks: List[str]
    dependencies: List[str]
    linked_bugs: List[str]
    issue_links: List[Dict[str, str]]  # [{"type": "is caused by", "target": "KEY-1"}, ...]
    created: datetime
    resolved: Optional[datetime]
    assignee: Optional[str]
    sprint: Optional[str]
    changelog: List[StatusTransition]


# ---------------------------------------------------------------------------
# Normalized ticket (output of pipeline)
# ---------------------------------------------------------------------------

@dataclass
class NormalizedTicket:
    key: str
    project: str
    # Classification
    normalized_type: NormalizedType
    size: Size
    size_confidence: Confidence
    area: Area
    area_confidence: Confidence
    # Timing
    created_at: datetime
    started_at: Optional[datetime]
    resolved_at: Optional[datetime]
    lead_time_days: Optional[float]
    cycle_time_days: Optional[float]
    backlog_wait_days: Optional[float]
    # Quality
    has_bug: bool
    has_rework: bool
    rework_confidence: Optional[Confidence]  # only set when has_rework=True
    is_duplicate: bool
    is_epic: bool
    # Metadata
    status_mapping_confidence: Confidence
    included_in_baseline: bool
    exclusion_reason: Optional[ExclusionReason]
    outcome: Outcome
    # Original data for traceability
    raw_summary: str
    raw_type: str
    raw_status: str


# ---------------------------------------------------------------------------
# Bucket key and metrics
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BucketKey:
    type: NormalizedType
    size: Size
    area: Area

    def __str__(self) -> str:
        return f"{self.type.value} / {self.size.value} / {self.area.value}"


@dataclass
class BucketMetrics:
    bucket: BucketKey
    sample_size: int
    median_cycle_time_days: Optional[float]
    p75_cycle_time_days: Optional[float]
    median_lead_time_days: Optional[float]
    median_backlog_wait_days: Optional[float]
    bug_rate: float
    rework_rate: float
    clean_completion_rate: float
    baseline_confidence: Confidence


# ---------------------------------------------------------------------------
# Summary output
# ---------------------------------------------------------------------------

@dataclass
class AnalysisSummary:
    project_key: str
    analysis_window_start: Optional[datetime]
    analysis_window_end: Optional[datetime]
    total_issues_fetched: int
    total_included_in_baseline: int
    total_excluded: int
    exclusion_breakdown: Dict[str, int]
    bucket_count: int
    high_confidence_buckets: int
    slow_buckets: List[BucketMetrics]  # top 5 by median cycle time
    quality_hotspots: List[BucketMetrics]  # top 5 by bug+rework rate
    # Data confidence overview
    data_quality: Dict[str, any]  # timing_coverage, status_mapping_quality, etc.
    # Narrative recommendations
    recommendations: List[str]
