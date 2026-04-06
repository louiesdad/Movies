"""
Complexity Analyzer — scores Jira tickets based on content, not just story points.

This is the "judgment" layer. It reads ticket content (description richness,
acceptance criteria count, subtasks, dependencies, type, labels) and produces
a normalized complexity score (0–100) that represents how inherently difficult
the work is — independent of how long it actually took.

Weight distribution (rebalanced to avoid over-weighting verbose descriptions):
  - Description richness:  0–15  (structural complexity of the spec)
  - Requirements depth:    0–15  (acceptance criteria + subtask burden)
  - Integration scope:     0–15  (dependencies + components touched)
  - Type complexity:       0–15  (inherent difficulty by ticket type)
  - Team estimate (pts):   0–25  (the team's own sizing — strongest signal)
  - Risk indicators:       0–15  (contextual keyword phrases)
  Total cap: 100
"""

from dataclasses import dataclass
from typing import List
from mock_data import JiraTicket


@dataclass
class ComplexityBreakdown:
    """Detailed breakdown of what contributed to the complexity score."""
    description_score: float     # 0–15: richness of description
    requirements_score: float    # 0–15: acceptance criteria + subtask count
    integration_score: float     # 0–15: dependencies + components
    type_score: float            # 0–15: inherent complexity of ticket type
    scope_score: float           # 0–25: story points as a proxy for team estimate
    risk_score: float            # 0–15: keywords indicating risk/uncertainty
    total: float                 # 0–100

    @property
    def category(self) -> str:
        if self.total <= 20:
            return "Trivial"
        elif self.total <= 40:
            return "Simple"
        elif self.total <= 60:
            return "Moderate"
        elif self.total <= 80:
            return "Complex"
        else:
            return "Highly Complex"


def _score_description(ticket: JiraTicket) -> float:
    """Score based on description length, structure, and richness (max 15)."""
    desc = ticket.description
    score = 0.0

    # Length — capped lower than before to reduce verbosity bias
    word_count = len(desc.split())
    if word_count < 20:
        score += 1
    elif word_count < 50:
        score += 3
    elif word_count < 100:
        score += 6
    elif word_count < 200:
        score += 9
    else:
        score += 11

    # Count unique structural marker *types* present (not occurrences)
    structure_markers = ["##", "- ", "* ", "```", "1.", "2.", "3."]
    unique_marker_types = sum(1 for m in structure_markers if m in desc)
    score += min(unique_marker_types * 0.7, 4.0)

    return min(score, 15.0)


def _score_requirements(ticket: JiraTicket) -> float:
    """Score based on acceptance criteria and subtask count (max 15)."""
    score = 0.0

    ac_count = len(ticket.acceptance_criteria)
    if ac_count <= 1:
        score += 1
    elif ac_count <= 3:
        score += 4
    elif ac_count <= 5:
        score += 7
    elif ac_count <= 8:
        score += 10
    else:
        score += 13

    subtask_count = len(ticket.subtasks)
    score += min(subtask_count * 0.4, 2.0)

    return min(score, 15.0)


def _score_integration(ticket: JiraTicket) -> float:
    """Score based on dependencies and component breadth (max 15)."""
    score = 0.0

    dep_count = len(ticket.dependencies)
    score += min(dep_count * 3.0, 9.0)

    comp_count = len(ticket.components)
    score += min(comp_count * 2.0, 6.0)

    return min(score, 15.0)


def _score_type(ticket: JiraTicket) -> float:
    """Different ticket types carry inherent complexity (max 15)."""
    type_scores = {
        "Bug": 5.0,       # Usually focused fix
        "Task": 4.0,      # Routine work
        "Spike": 8.0,     # Research = uncertainty
        "Story": 10.0,    # Feature work with unknowns
        "Epic": 14.0,     # Large scope
    }
    base = type_scores.get(ticket.type, 7.0)

    # Bugs with specific technical challenges are harder
    hard_bug_keywords = ["race condition", "concurrency", "memory leak",
                          "deadlock", "corruption", "intermittent", "flaky"]
    if ticket.type == "Bug":
        desc_lower = ticket.description.lower()
        keyword_hits = sum(1 for kw in hard_bug_keywords if kw in desc_lower)
        base += min(keyword_hits * 3.0, 9.0)

    return min(base, 15.0)


def _score_scope(ticket: JiraTicket) -> float:
    """Use story points as the team's own complexity estimate (max 25).

    This is the strongest signal — the team already evaluated complexity
    during planning. We use a logarithmic-ish curve so that large epics
    (21+ points) get meaningfully more weight than small tasks.
    """
    points = ticket.story_points or 1
    if points <= 1:
        return 3.0
    elif points <= 2:
        return 6.0
    elif points <= 3:
        return 9.0
    elif points <= 5:
        return 13.0
    elif points <= 8:
        return 16.0
    elif points <= 13:
        return 20.0
    elif points <= 21:
        return 23.0
    else:
        return 25.0


# Risk phrases scored by context — each is a (phrase, weight) pair.
# Higher weight for phrases that unambiguously signal difficulty.
_RISK_PHRASES = [
    # High-signal risk (weight 3.0)
    ("breaking change", 3.0),
    ("data loss", 3.0),
    ("race condition", 3.0),
    ("backwardcompat", 3.0),
    # Medium-signal risk (weight 2.0)
    ("migrate", 2.0),         # covers "migration", "migrate from"
    ("deprecat", 2.0),        # covers "deprecated", "deprecation"
    ("rollback", 2.0),
    ("pci", 2.0),
    ("compliance", 2.0),
    ("real-time", 2.0),
    ("streaming", 2.0),
    ("distributed", 2.0),
    ("downtime", 2.0),
    ("incident", 2.0),
    # Lower-signal risk (weight 1.0) — common in positive contexts too
    ("security", 1.0),
    ("encryption", 1.0),
    ("third-party", 1.0),
    ("external api", 1.0),
    ("latency", 1.0),
    ("throughput", 1.0),
]


def _score_risk(ticket: JiraTicket) -> float:
    """Detect risk/uncertainty indicators using weighted phrase matching (max 15).

    Uses phrase-level matching with context-aware weights to reduce false
    positives. High-signal phrases like "breaking change" score more than
    ambiguous words like "security".

    For Bug tickets, excludes phrases already scored by _score_type's
    hard_bug_keywords to prevent double-counting.
    """
    # Phrases already scored in _score_type for Bugs
    _BUG_OVERLAP = {"race condition"}

    combined_text = (ticket.summary + " " + ticket.description).lower()
    weighted_score = sum(
        weight for phrase, weight in _RISK_PHRASES
        if phrase in combined_text
        and not (ticket.type == "Bug" and phrase in _BUG_OVERLAP)
    )
    return min(weighted_score, 15.0)


def analyze_complexity(ticket: JiraTicket) -> ComplexityBreakdown:
    """Produce a full complexity breakdown for a single ticket."""
    desc = _score_description(ticket)
    reqs = _score_requirements(ticket)
    integ = _score_integration(ticket)
    ttype = _score_type(ticket)
    scope = _score_scope(ticket)
    risk = _score_risk(ticket)
    total = desc + reqs + integ + ttype + scope + risk

    return ComplexityBreakdown(
        description_score=round(desc, 1),
        requirements_score=round(reqs, 1),
        integration_score=round(integ, 1),
        type_score=round(ttype, 1),
        scope_score=round(scope, 1),
        risk_score=round(risk, 1),
        total=round(min(total, 100.0), 1),
    )


def analyze_batch(tickets: List[JiraTicket]) -> List[tuple]:
    """Return (ticket, complexity_breakdown) pairs for a list of tickets."""
    return [(t, analyze_complexity(t)) for t in tickets]
