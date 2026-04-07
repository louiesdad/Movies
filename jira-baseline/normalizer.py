"""
Normalizer — maps raw Jira issue types and statuses to canonical values.
"""

from typing import Dict, List, Optional, Tuple

from models import (
    NormalizedType, Phase, StatusMapping, Confidence,
)
from config import ProjectConfig


# ---------------------------------------------------------------------------
# Type normalization
# ---------------------------------------------------------------------------

_TYPE_MAP: Dict[str, NormalizedType] = {
    "bug": NormalizedType.BUG,
    "defect": NormalizedType.BUG,
    "incident": NormalizedType.BUG,
    "task": NormalizedType.TASK,
    "chore": NormalizedType.TASK,
    "maintenance": NormalizedType.TASK,
    "sub-task": NormalizedType.TASK,
    "subtask": NormalizedType.TASK,
    "story": NormalizedType.STORY,
    "feature": NormalizedType.STORY,
    "user story": NormalizedType.STORY,
    "spike": NormalizedType.SPIKE,
    "research": NormalizedType.SPIKE,
    "epic": NormalizedType.OTHER,  # handled specially via is_epic
}


def normalize_type(raw_type: str) -> NormalizedType:
    """Map a raw Jira issue type to a normalized type."""
    return _TYPE_MAP.get(raw_type.lower().strip(), NormalizedType.OTHER)


def is_epic_type(raw_type: str) -> bool:
    """Check if a raw type is an Epic."""
    return raw_type.lower().strip() == "epic"


# ---------------------------------------------------------------------------
# Status normalization (two-pass: phase + blocked modifier)
# ---------------------------------------------------------------------------

_PHASE_RULES: List[Tuple[str, Phase, float]] = [
    # DONE
    ("closed", Phase.DONE, 0.95),
    ("done", Phase.DONE, 0.95),
    ("resolved", Phase.DONE, 0.95),
    ("completed", Phase.DONE, 0.95),
    ("released", Phase.DONE, 0.90),
    ("deployed", Phase.DONE, 0.90),
    ("shipped", Phase.DONE, 0.90),
    ("verified", Phase.DONE, 0.85),
    ("accepted", Phase.DONE, 0.85),
    ("archived", Phase.DONE, 0.85),
    ("won't do", Phase.DONE, 0.80),
    ("wont do", Phase.DONE, 0.80),
    ("won't fix", Phase.DONE, 0.80),
    ("wontfix", Phase.DONE, 0.80),
    ("cancelled", Phase.DONE, 0.80),
    ("canceled", Phase.DONE, 0.80),
    ("duplicate", Phase.DONE, 0.80),
    # REVIEW
    ("in review", Phase.REVIEW, 0.95),
    ("code review", Phase.REVIEW, 0.95),
    ("peer review", Phase.REVIEW, 0.95),
    ("pr review", Phase.REVIEW, 0.95),
    ("pull request", Phase.REVIEW, 0.90),
    ("awaiting review", Phase.REVIEW, 0.90),
    ("pending review", Phase.REVIEW, 0.90),
    ("in qa", Phase.REVIEW, 0.90),
    ("qa review", Phase.REVIEW, 0.90),
    ("in test", Phase.REVIEW, 0.90),
    ("testing", Phase.REVIEW, 0.90),
    ("in testing", Phase.REVIEW, 0.90),
    ("quality assurance", Phase.REVIEW, 0.90),
    ("uat", Phase.REVIEW, 0.85),
    ("user acceptance", Phase.REVIEW, 0.85),
    ("staging", Phase.REVIEW, 0.85),
    ("in staging", Phase.REVIEW, 0.85),
    ("awaiting approval", Phase.REVIEW, 0.85),
    ("pending approval", Phase.REVIEW, 0.85),
    ("waiting for approval", Phase.REVIEW, 0.85),
    ("sign-off", Phase.REVIEW, 0.85),
    ("signoff", Phase.REVIEW, 0.85),
    ("validation", Phase.REVIEW, 0.80),
    ("review", Phase.REVIEW, 0.75),
    # ACTIVE
    ("in progress", Phase.ACTIVE, 0.95),
    ("in development", Phase.ACTIVE, 0.95),
    ("in dev", Phase.ACTIVE, 0.95),
    ("developing", Phase.ACTIVE, 0.90),
    ("coding", Phase.ACTIVE, 0.90),
    ("work in progress", Phase.ACTIVE, 0.90),
    ("implementation", Phase.ACTIVE, 0.85),
    ("implementing", Phase.ACTIVE, 0.85),
    ("working on", Phase.ACTIVE, 0.85),
    ("in flight", Phase.ACTIVE, 0.80),
    ("wip", Phase.ACTIVE, 0.80),
    ("active", Phase.ACTIVE, 0.80),
    ("started", Phase.ACTIVE, 0.75),
    # READY
    ("ready for dev", Phase.READY, 0.95),
    ("ready for development", Phase.READY, 0.95),
    ("ready to start", Phase.READY, 0.90),
    ("selected for dev", Phase.READY, 0.90),
    ("selected for development", Phase.READY, 0.90),
    ("sprint ready", Phase.READY, 0.90),
    ("groomed", Phase.READY, 0.85),
    ("refined", Phase.READY, 0.85),
    ("to do", Phase.READY, 0.85),
    ("todo", Phase.READY, 0.85),
    ("committed", Phase.READY, 0.80),
    ("prioritized", Phase.READY, 0.75),
    ("open", Phase.READY, 0.70),
    ("ready", Phase.READY, 0.70),
    ("new", Phase.READY, 0.65),
    # BACKLOG
    ("backlog", Phase.BACKLOG, 0.95),
    ("icebox", Phase.BACKLOG, 0.90),
    ("parking lot", Phase.BACKLOG, 0.85),
    ("awaiting triage", Phase.BACKLOG, 0.85),
    ("triage", Phase.BACKLOG, 0.80),
    ("someday", Phase.BACKLOG, 0.80),
    ("future", Phase.BACKLOG, 0.75),
    ("ideas", Phase.BACKLOG, 0.75),
    ("funnel", Phase.BACKLOG, 0.75),
    ("unassigned", Phase.BACKLOG, 0.70),
]

_BLOCKED_KEYWORDS: List[Tuple[str, float]] = [
    ("blocked", 0.90),
    ("on hold", 0.90),
    ("paused", 0.85),
    ("suspended", 0.85),
    ("stalled", 0.85),
    ("waiting for info", 0.85),
    ("impediment", 0.85),
    ("waiting", 0.80),
    ("dependency", 0.75),
    ("pending", 0.70),
    ("deferred", 0.80),
]


class StatusNormalizer:
    """Two-pass status normalizer: phase match + blocked modifier."""

    def __init__(self, overrides: Optional[Dict[str, str]] = None,
                 extra_done_statuses: Optional[List[str]] = None):
        self._overrides: Dict[str, Phase] = {}
        self._invalid_overrides: List[str] = []
        if overrides:
            for raw, phase_str in overrides.items():
                try:
                    self._overrides[raw.lower().strip()] = Phase(phase_str.lower().strip())
                except ValueError:
                    self._invalid_overrides.append(
                        f"'{raw}': invalid phase '{phase_str}'"
                    )
        # Inject additional done statuses from config
        if extra_done_statuses:
            for status in extra_done_statuses:
                key = status.lower().strip()
                if key not in self._overrides:
                    self._overrides[key] = Phase.DONE
        self._cache: Dict[str, StatusMapping] = {}

    def map(self, raw_status: str) -> StatusMapping:
        key = raw_status.lower().strip()
        if key in self._cache:
            return self._cache[key]
        result = self._do_map(raw_status, key)
        self._cache[key] = result
        return result

    def _do_map(self, raw_status: str, key: str) -> StatusMapping:
        # Manual overrides
        if key in self._overrides:
            return StatusMapping(
                raw_status=raw_status,
                phase=self._overrides[key],
                confidence=1.0,
                is_blocked=False,
                matched_keyword="(override)",
            )

        # Pass 1: best non-blocked phase match (longest keyword wins)
        best_phase = None
        best_specificity = 0
        for keyword, phase, confidence in _PHASE_RULES:
            if keyword in key and len(keyword) > best_specificity:
                best_specificity = len(keyword)
                best_phase = (keyword, phase, confidence)

        # Pass 2: check blocked modifiers independently
        is_blocked = False
        for blocked_kw, _ in _BLOCKED_KEYWORDS:
            if blocked_kw in key:
                is_blocked = True
                break

        if best_phase:
            kw, phase, conf = best_phase
            return StatusMapping(
                raw_status=raw_status, phase=phase,
                confidence=conf, is_blocked=is_blocked,
                matched_keyword=kw,
            )

        # Blocked-only (no phase match) — default to ACTIVE
        if is_blocked:
            return StatusMapping(
                raw_status=raw_status, phase=Phase.ACTIVE,
                confidence=0.70, is_blocked=True,
                matched_keyword="(blocked-only)",
            )

        return StatusMapping(
            raw_status=raw_status, phase=Phase.UNKNOWN,
            confidence=0.0, is_blocked=False,
            matched_keyword="(no match)",
        )

    def is_done(self, raw_status: str) -> bool:
        return self.map(raw_status).phase == Phase.DONE

    def is_active_or_review(self, raw_status: str) -> bool:
        return self.map(raw_status).phase in (Phase.ACTIVE, Phase.REVIEW)

    def is_duplicate_resolution(self, resolution: Optional[str]) -> bool:
        if not resolution:
            return False
        return "duplicate" in resolution.lower()

    def is_duplicate_status(self, raw_status: str) -> bool:
        """Check if a status itself indicates duplicate (e.g. status='Duplicate')."""
        return "duplicate" in raw_status.lower()
