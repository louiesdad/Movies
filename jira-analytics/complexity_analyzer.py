"""
Complexity Analyzer — scores Jira tickets based on content, not just story points.

This is the "judgment" layer. It reads ticket content (description richness,
acceptance criteria count, subtasks, dependencies, type, labels) and produces
a normalized complexity score (0–100) that represents how inherently difficult
the work is — independent of how long it actually took.
"""

from dataclasses import dataclass
from typing import List
from mock_data import JiraTicket


@dataclass
class ComplexityBreakdown:
    """Detailed breakdown of what contributed to the complexity score."""
    description_score: float     # 0–20: richness of description
    requirements_score: float    # 0–20: acceptance criteria + subtask count
    integration_score: float     # 0–15: dependencies + components
    type_score: float            # 0–15: inherent complexity of ticket type
    scope_score: float           # 0–15: story points as a proxy for team estimate
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
    """Score based on description length, structure, and richness."""
    desc = ticket.description
    score = 0.0

    # Length (longer descriptions usually mean more requirements)
    word_count = len(desc.split())
    if word_count < 20:
        score += 2
    elif word_count < 50:
        score += 5
    elif word_count < 100:
        score += 10
    elif word_count < 200:
        score += 14
    else:
        score += 18

    # Structure markers (headers, lists, code blocks)
    structure_markers = ["##", "- ", "* ", "```", "1.", "2.", "3."]
    marker_count = sum(1 for m in structure_markers if m in desc)
    score += min(marker_count * 0.5, 2.0)

    return min(score, 20.0)


def _score_requirements(ticket: JiraTicket) -> float:
    """Score based on acceptance criteria and subtask count."""
    score = 0.0

    ac_count = len(ticket.acceptance_criteria)
    if ac_count <= 1:
        score += 2
    elif ac_count <= 3:
        score += 6
    elif ac_count <= 5:
        score += 10
    elif ac_count <= 8:
        score += 14
    else:
        score += 18

    subtask_count = len(ticket.subtasks)
    score += min(subtask_count * 0.5, 2.0)

    return min(score, 20.0)


def _score_integration(ticket: JiraTicket) -> float:
    """Score based on dependencies and component breadth."""
    score = 0.0

    dep_count = len(ticket.dependencies)
    score += min(dep_count * 3.0, 9.0)

    comp_count = len(ticket.components)
    score += min(comp_count * 2.0, 6.0)

    return min(score, 15.0)


def _score_type(ticket: JiraTicket) -> float:
    """Different ticket types carry inherent complexity."""
    type_scores = {
        "Bug": 5.0,       # Usually focused fix
        "Task": 4.0,      # Routine work
        "Spike": 8.0,     # Research = uncertainty
        "Story": 10.0,    # Feature work with unknowns
        "Epic": 14.0,     # Large scope
    }
    base = type_scores.get(ticket.type, 7.0)

    # Bugs with words like "race condition", "memory leak" are harder
    hard_bug_keywords = ["race condition", "concurrency", "memory leak",
                          "deadlock", "corruption", "intermittent", "flaky"]
    if ticket.type == "Bug":
        desc_lower = ticket.description.lower()
        keyword_hits = sum(1 for kw in hard_bug_keywords if kw in desc_lower)
        base += min(keyword_hits * 3.0, 9.0)

    return min(base, 15.0)


def _score_scope(ticket: JiraTicket) -> float:
    """Use story points as the team's own complexity estimate."""
    points = ticket.story_points or 1
    if points <= 1:
        return 2.0
    elif points <= 2:
        return 4.0
    elif points <= 3:
        return 6.0
    elif points <= 5:
        return 8.0
    elif points <= 8:
        return 10.0
    elif points <= 13:
        return 12.0
    else:
        return 15.0


def _score_risk(ticket: JiraTicket) -> float:
    """Detect risk/uncertainty indicators in the ticket content."""
    risk_keywords = [
        "migration", "deprecat", "rollback", "breaking change",
        "security", "pci", "compliance", "audit",
        "real-time", "streaming", "distributed",
        "performance", "latency", "throughput",
        "third-party", "external api", "vendor",
        "data loss", "downtime", "incident",
        "encryption", "secrets", "credential",
    ]
    combined_text = (ticket.summary + " " + ticket.description).lower()
    hits = sum(1 for kw in risk_keywords if kw in combined_text)
    return min(hits * 2.5, 15.0)


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
