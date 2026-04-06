"""
Status Mapper — intelligently normalizes custom Jira statuses and swimlanes
to a standard lifecycle model.

Real Jira instances have wildly customized workflows:
  - "In Review", "Code Review", "Peer Check" → all mean REVIEW
  - "Ready for Dev", "Backlog", "Selected for Development" → all mean BACKLOG
  - "Deployed", "Closed", "Released", "Verified" → all mean DONE

This module uses keyword-based heuristics with confidence scoring to map
any custom status string to one of 5 normalized phases:

  BACKLOG → READY → ACTIVE → REVIEW → DONE

It also detects blocked/waiting states as a modifier on any phase.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Phase(Enum):
    """Normalized lifecycle phases."""
    BACKLOG = "backlog"    # Not yet ready to start
    READY = "ready"        # Groomed, ready to be picked up
    ACTIVE = "active"      # Actively being worked on
    REVIEW = "review"      # Code review, QA, UAT, approval
    DONE = "done"          # Completed, deployed, closed
    UNKNOWN = "unknown"    # Could not determine


@dataclass
class StatusMapping:
    """Result of mapping a raw status string to a normalized phase."""
    raw_status: str
    phase: Phase
    confidence: float      # 0.0–1.0, how sure we are about this mapping
    is_blocked: bool       # True if status indicates a blocked/waiting state
    matched_keyword: str   # Which keyword triggered the match


# ---------------------------------------------------------------------------
# Keyword rules: (keyword_or_phrase, phase, confidence, is_blocked)
#
# Ordered by specificity — more specific phrases first so they match before
# generic ones. Matching is case-insensitive substring.
# ---------------------------------------------------------------------------

_RULES: List[Tuple[str, Phase, float, bool]] = [
    # ---- DONE (highest confidence — most unambiguous) ----
    ("closed",              Phase.DONE,    0.95, False),
    ("done",                Phase.DONE,    0.95, False),
    ("resolved",            Phase.DONE,    0.95, False),
    ("completed",           Phase.DONE,    0.95, False),
    ("released",            Phase.DONE,    0.90, False),
    ("deployed",            Phase.DONE,    0.90, False),
    ("shipped",             Phase.DONE,    0.90, False),
    ("verified",            Phase.DONE,    0.85, False),
    ("accepted",            Phase.DONE,    0.85, False),
    ("archived",            Phase.DONE,    0.85, False),
    ("won't do",            Phase.DONE,    0.80, False),
    ("wont do",             Phase.DONE,    0.80, False),
    ("won't fix",           Phase.DONE,    0.80, False),
    ("wontfix",             Phase.DONE,    0.80, False),
    ("cancelled",           Phase.DONE,    0.80, False),
    ("canceled",            Phase.DONE,    0.80, False),
    ("duplicate",           Phase.DONE,    0.80, False),

    # ---- REVIEW ----
    ("in review",           Phase.REVIEW,  0.95, False),
    ("code review",         Phase.REVIEW,  0.95, False),
    ("peer review",         Phase.REVIEW,  0.95, False),
    ("pr review",           Phase.REVIEW,  0.95, False),
    ("pull request",        Phase.REVIEW,  0.90, False),
    ("awaiting review",     Phase.REVIEW,  0.90, False),
    ("pending review",      Phase.REVIEW,  0.90, False),
    ("in qa",               Phase.REVIEW,  0.90, False),
    ("qa review",           Phase.REVIEW,  0.90, False),
    ("in test",             Phase.REVIEW,  0.90, False),
    ("testing",             Phase.REVIEW,  0.90, False),
    ("in testing",          Phase.REVIEW,  0.90, False),
    ("quality assurance",   Phase.REVIEW,  0.90, False),
    ("uat",                 Phase.REVIEW,  0.85, False),
    ("user acceptance",     Phase.REVIEW,  0.85, False),
    ("staging",             Phase.REVIEW,  0.85, False),
    ("in staging",          Phase.REVIEW,  0.85, False),
    ("awaiting approval",   Phase.REVIEW,  0.85, False),
    ("pending approval",    Phase.REVIEW,  0.85, False),
    ("sign-off",            Phase.REVIEW,  0.85, False),
    ("signoff",             Phase.REVIEW,  0.85, False),
    ("validation",          Phase.REVIEW,  0.80, False),
    ("review",              Phase.REVIEW,  0.75, False),  # generic fallback

    # ---- ACTIVE ----
    ("in progress",         Phase.ACTIVE,  0.95, False),
    ("in development",      Phase.ACTIVE,  0.95, False),
    ("in dev",              Phase.ACTIVE,  0.95, False),
    ("developing",          Phase.ACTIVE,  0.90, False),
    ("coding",              Phase.ACTIVE,  0.90, False),
    ("implementation",      Phase.ACTIVE,  0.85, False),
    ("implementing",        Phase.ACTIVE,  0.85, False),
    ("working on",          Phase.ACTIVE,  0.85, False),
    ("active",              Phase.ACTIVE,  0.80, False),
    ("started",             Phase.ACTIVE,  0.75, False),
    ("in flight",           Phase.ACTIVE,  0.80, False),
    ("wip",                 Phase.ACTIVE,  0.80, False),
    ("work in progress",    Phase.ACTIVE,  0.90, False),

    # ---- READY ----
    ("ready for dev",       Phase.READY,   0.95, False),
    ("ready for development", Phase.READY, 0.95, False),
    ("ready to start",      Phase.READY,   0.90, False),
    ("selected for dev",    Phase.READY,   0.90, False),
    ("selected for development", Phase.READY, 0.90, False),
    ("sprint ready",        Phase.READY,   0.90, False),
    ("groomed",             Phase.READY,   0.85, False),
    ("refined",             Phase.READY,   0.85, False),
    ("committed",           Phase.READY,   0.80, False),
    ("prioritized",         Phase.READY,   0.75, False),
    ("ready",               Phase.READY,   0.70, False),  # generic
    ("to do",               Phase.READY,   0.85, False),
    ("todo",                Phase.READY,   0.85, False),
    ("open",                Phase.READY,   0.70, False),
    ("new",                 Phase.READY,   0.65, False),

    # ---- BACKLOG ----
    ("backlog",             Phase.BACKLOG, 0.95, False),
    ("icebox",              Phase.BACKLOG, 0.90, False),
    ("parking lot",         Phase.BACKLOG, 0.85, False),
    ("someday",             Phase.BACKLOG, 0.80, False),
    ("future",              Phase.BACKLOG, 0.75, False),
    ("ideas",               Phase.BACKLOG, 0.75, False),
    ("triage",              Phase.BACKLOG, 0.80, False),
    ("awaiting triage",     Phase.BACKLOG, 0.85, False),
    ("unassigned",          Phase.BACKLOG, 0.70, False),
    ("funnel",              Phase.BACKLOG, 0.75, False),

    # ---- BLOCKED (modifier — these indicate waiting/blocked on any phase) ----
    ("blocked",             Phase.ACTIVE,  0.90, True),
    ("on hold",             Phase.ACTIVE,  0.90, True),
    ("waiting",             Phase.ACTIVE,  0.80, True),
    ("pending",             Phase.ACTIVE,  0.70, True),
    ("waiting for info",    Phase.ACTIVE,  0.85, True),
    ("impediment",          Phase.ACTIVE,  0.85, True),
    ("dependency",          Phase.ACTIVE,  0.75, True),
    ("paused",              Phase.ACTIVE,  0.85, True),
    ("suspended",           Phase.ACTIVE,  0.85, True),
    ("stalled",             Phase.ACTIVE,  0.85, True),
    ("deferred",            Phase.BACKLOG, 0.80, True),
]


class StatusMapper:
    """Maps custom Jira status strings to normalized lifecycle phases.

    Usage:
        mapper = StatusMapper()
        result = mapper.map("In Peer Review")
        # result.phase == Phase.REVIEW, confidence=0.95

        # With custom overrides for org-specific statuses:
        mapper = StatusMapper(overrides={
            "Baking": Phase.REVIEW,    # org uses "Baking" for staging
            "Chilling": Phase.BACKLOG, # org uses "Chilling" for icebox
        })
    """

    def __init__(self, overrides: Optional[Dict[str, Phase]] = None):
        self._overrides = {k.lower().strip(): v for k, v in (overrides or {}).items()}
        self._cache: Dict[str, StatusMapping] = {}

    def map(self, raw_status: str) -> StatusMapping:
        """Map a raw status string to a normalized phase."""
        key = raw_status.lower().strip()

        if key in self._cache:
            return self._cache[key]

        result = self._do_map(raw_status, key)
        self._cache[key] = result
        return result

    def _do_map(self, raw_status: str, key: str) -> StatusMapping:
        # Check manual overrides first (confidence=1.0)
        if key in self._overrides:
            return StatusMapping(
                raw_status=raw_status,
                phase=self._overrides[key],
                confidence=1.0,
                is_blocked=False,
                matched_keyword="(manual override)",
            )

        # Try keyword rules — longer/more specific phrases first
        best_match: Optional[StatusMapping] = None
        best_specificity = 0

        for keyword, phase, confidence, is_blocked in _RULES:
            if keyword in key:
                # Prefer longer keyword matches (more specific)
                specificity = len(keyword)
                if specificity > best_specificity:
                    best_specificity = specificity
                    best_match = StatusMapping(
                        raw_status=raw_status,
                        phase=phase,
                        confidence=confidence,
                        is_blocked=is_blocked,
                        matched_keyword=keyword,
                    )

        if best_match:
            return best_match

        # No match — return unknown
        return StatusMapping(
            raw_status=raw_status,
            phase=Phase.UNKNOWN,
            confidence=0.0,
            is_blocked=False,
            matched_keyword="(no match)",
        )

    def map_batch(self, statuses: List[str]) -> Dict[str, StatusMapping]:
        """Map a list of status strings, return {raw_status: mapping}."""
        return {s: self.map(s) for s in statuses}

    def is_completed(self, raw_status: str) -> bool:
        """Check if a status indicates completion."""
        return self.map(raw_status).phase == Phase.DONE

    def is_active(self, raw_status: str) -> bool:
        """Check if a status indicates active work (ACTIVE or REVIEW)."""
        return self.map(raw_status).phase in (Phase.ACTIVE, Phase.REVIEW)

    def is_waiting(self, raw_status: str) -> bool:
        """Check if a status indicates backlog/ready (not started)."""
        return self.map(raw_status).phase in (Phase.BACKLOG, Phase.READY)

    def print_mapping_report(self, statuses: List[str]):
        """Print a diagnostic report showing how each status was mapped."""
        mappings = self.map_batch(statuses)
        unique = {}
        for s, m in mappings.items():
            key = s.lower().strip()
            if key not in unique:
                unique[key] = m

        print(f"\n  Status Mapping Report ({len(unique)} unique statuses)\n")
        print(f"  {'Raw Status':<30} {'Phase':<10} {'Conf':>5} {'Blocked':>8} {'Matched':>20}")
        print(f"  {'─'*30} {'─'*10} {'─'*5} {'─'*8} {'─'*20}")

        for m in sorted(unique.values(), key=lambda x: (x.phase.value, -x.confidence)):
            blocked = "YES" if m.is_blocked else ""
            conf = f"{m.confidence:.0%}"
            print(f"  {m.raw_status:<30} {m.phase.value:<10} {conf:>5} {blocked:>8} {m.matched_keyword:>20}")

        # Warn about low-confidence or unknown mappings
        low_conf = [m for m in unique.values() if m.confidence < 0.7 and m.phase != Phase.UNKNOWN]
        unknown = [m for m in unique.values() if m.phase == Phase.UNKNOWN]
        if low_conf:
            print(f"\n  WARNING: {len(low_conf)} status(es) mapped with low confidence (<70%).")
            print(f"  Consider adding manual overrides for these.")
        if unknown:
            print(f"\n  WARNING: {len(unknown)} status(es) could not be mapped.")
            for m in unknown:
                print(f"    - \"{m.raw_status}\" → add to overrides dict")
