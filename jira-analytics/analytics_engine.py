"""
Analytics Engine — computes statistics from complexity-scored tickets.

Key concept: RELATIVE VELOCITY
  Raw velocity = cycle_time / story_points  (days per point)
  Complexity-adjusted velocity = cycle_time / complexity_score

  This lets you compare: "Was a 2-week complex migration actually faster,
  relatively speaking, than a 1-day simple bug fix?"

  A lower complexity-adjusted velocity means better throughput per unit
  of real difficulty.
"""

import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from mock_data import JiraTicket
from complexity_analyzer import ComplexityBreakdown, analyze_complexity


@dataclass
class TicketAnalysis:
    """Full analysis of a single ticket."""
    ticket: JiraTicket
    complexity: ComplexityBreakdown
    cycle_time_days: Optional[float]
    lead_time_days: Optional[float]
    defect_count: int
    unresolved_defect_count: int
    raw_velocity: Optional[float]           # days per story point
    complexity_adjusted_velocity: Optional[float]  # cycle_time / complexity
    relative_efficiency: Optional[str]       # qualitative rating


@dataclass
class ProjectStats:
    """Aggregate statistics for a project."""
    project_key: str
    project_name: str
    total_tickets: int
    completed_tickets: int
    # Cycle time
    avg_cycle_time: float
    min_cycle_time: float
    max_cycle_time: float
    median_cycle_time: float
    # Lead time
    avg_lead_time: float
    min_lead_time: float
    max_lead_time: float
    # Defects
    total_defects: int
    avg_defects_per_ticket: float
    min_defects: int
    max_defects: int
    defect_density_by_complexity: Dict[str, float]  # category -> avg defects
    # Quality
    defect_free_rate: float   # % of tickets with zero defects
    critical_defect_rate: float
    # Velocity
    avg_raw_velocity: float
    avg_adjusted_velocity: float
    # By type
    stats_by_type: Dict[str, dict]
    # By complexity category
    stats_by_complexity: Dict[str, dict]
    # Top performers and concerns
    fastest_relative: List[TicketAnalysis]
    slowest_relative: List[TicketAnalysis]
    highest_quality: List[TicketAnalysis]    # complex but few defects
    riskiest: List[TicketAnalysis]           # high defects relative to complexity


def _rate_efficiency(adjusted_velocity: float, avg_adjusted: float) -> str:
    """Rate a ticket's efficiency relative to the project average."""
    if adjusted_velocity <= avg_adjusted * 0.5:
        return "Exceptional"
    elif adjusted_velocity <= avg_adjusted * 0.8:
        return "Above Average"
    elif adjusted_velocity <= avg_adjusted * 1.2:
        return "Average"
    elif adjusted_velocity <= avg_adjusted * 1.5:
        return "Below Average"
    else:
        return "Slow"


def analyze_project(tickets: List[JiraTicket], project_key: str,
                     project_name: str) -> ProjectStats:
    """Run full analysis on a project's tickets."""

    # Score complexity for all tickets
    analyses: List[TicketAnalysis] = []
    for ticket in tickets:
        cx = analyze_complexity(ticket)
        ct = ticket.cycle_time_days
        lt = ticket.lead_time_days
        defects = ticket.linked_defects
        defect_count = len(defects)
        unresolved = sum(1 for d in defects if not d.resolved)
        raw_vel = (ct / ticket.story_points) if ct and ticket.story_points else None
        adj_vel = (ct / cx.total) if ct and cx.total > 0 else None

        analyses.append(TicketAnalysis(
            ticket=ticket,
            complexity=cx,
            cycle_time_days=ct,
            lead_time_days=lt,
            defect_count=defect_count,
            unresolved_defect_count=unresolved,
            raw_velocity=raw_vel,
            complexity_adjusted_velocity=adj_vel,
            relative_efficiency=None,  # set after computing average
        ))

    # Filter to completed tickets for time-based stats
    completed = [a for a in analyses if a.cycle_time_days is not None]
    if not completed:
        raise ValueError(f"No completed tickets found for {project_key}")

    # Compute average adjusted velocity for efficiency rating
    adj_vels = [a.complexity_adjusted_velocity for a in completed
                if a.complexity_adjusted_velocity]
    avg_adj_vel = statistics.mean(adj_vels) if adj_vels else 1.0

    # Now rate each ticket
    for a in completed:
        if a.complexity_adjusted_velocity:
            a.relative_efficiency = _rate_efficiency(
                a.complexity_adjusted_velocity, avg_adj_vel
            )

    cycle_times = [a.cycle_time_days for a in completed]
    lead_times = [a.lead_time_days for a in completed if a.lead_time_days]
    raw_vels = [a.raw_velocity for a in completed if a.raw_velocity]

    # Defect stats
    defect_counts = [a.defect_count for a in completed]
    defect_free = sum(1 for d in defect_counts if d == 0)
    critical_defects = sum(
        1 for a in completed
        for d in a.ticket.linked_defects
        if d.severity == "critical"
    )

    # Stats by ticket type
    stats_by_type: Dict[str, dict] = {}
    for ttype in set(a.ticket.type for a in completed):
        type_items = [a for a in completed if a.ticket.type == ttype]
        type_cts = [a.cycle_time_days for a in type_items]
        type_defects = [a.defect_count for a in type_items]
        type_adj = [a.complexity_adjusted_velocity for a in type_items
                     if a.complexity_adjusted_velocity]
        type_complexities = [a.complexity.total for a in type_items]
        stats_by_type[ttype] = {
            "count": len(type_items),
            "avg_cycle_time": round(statistics.mean(type_cts), 1),
            "avg_defects": round(statistics.mean(type_defects), 2),
            "avg_complexity": round(statistics.mean(type_complexities), 1),
            "avg_adjusted_velocity": round(statistics.mean(type_adj), 3) if type_adj else None,
        }

    # Stats by complexity category
    stats_by_complexity: Dict[str, dict] = {}
    for cat in ["Trivial", "Simple", "Moderate", "Complex", "Highly Complex"]:
        cat_items = [a for a in completed if a.complexity.category == cat]
        if not cat_items:
            continue
        cat_cts = [a.cycle_time_days for a in cat_items]
        cat_defects = [a.defect_count for a in cat_items]
        cat_adj = [a.complexity_adjusted_velocity for a in cat_items
                    if a.complexity_adjusted_velocity]
        stats_by_complexity[cat] = {
            "count": len(cat_items),
            "avg_cycle_time": round(statistics.mean(cat_cts), 1),
            "median_cycle_time": round(statistics.median(cat_cts), 1),
            "avg_defects": round(statistics.mean(cat_defects), 2),
            "avg_adjusted_velocity": round(statistics.mean(cat_adj), 3) if cat_adj else None,
        }

    # Defect density by complexity
    defect_density: Dict[str, float] = {}
    for cat, data in stats_by_complexity.items():
        defect_density[cat] = data["avg_defects"]

    # Top performers (lowest adjusted velocity = fastest relative to complexity)
    sorted_by_vel = sorted(
        [a for a in completed if a.complexity_adjusted_velocity],
        key=lambda a: a.complexity_adjusted_velocity,
    )
    fastest = sorted_by_vel[:5]
    slowest = sorted_by_vel[-5:]

    # Highest quality: complex tickets with few defects
    complex_tickets = [a for a in completed if a.complexity.total >= 50]
    highest_quality = sorted(complex_tickets, key=lambda a: a.defect_count)[:5]

    # Riskiest: high defect count relative to complexity
    riskiest = sorted(
        completed,
        key=lambda a: a.defect_count / max(a.complexity.total, 1),
        reverse=True,
    )[:5]

    return ProjectStats(
        project_key=project_key,
        project_name=project_name,
        total_tickets=len(analyses),
        completed_tickets=len(completed),
        avg_cycle_time=round(statistics.mean(cycle_times), 1),
        min_cycle_time=round(min(cycle_times), 1),
        max_cycle_time=round(max(cycle_times), 1),
        median_cycle_time=round(statistics.median(cycle_times), 1),
        avg_lead_time=round(statistics.mean(lead_times), 1) if lead_times else 0,
        min_lead_time=round(min(lead_times), 1) if lead_times else 0,
        max_lead_time=round(max(lead_times), 1) if lead_times else 0,
        total_defects=sum(defect_counts),
        avg_defects_per_ticket=round(statistics.mean(defect_counts), 2),
        min_defects=min(defect_counts),
        max_defects=max(defect_counts),
        defect_density_by_complexity=defect_density,
        defect_free_rate=round(defect_free / len(completed) * 100, 1),
        critical_defect_rate=round(critical_defects / max(sum(defect_counts), 1) * 100, 1),
        avg_raw_velocity=round(statistics.mean(raw_vels), 2) if raw_vels else 0,
        avg_adjusted_velocity=round(avg_adj_vel, 3),
        stats_by_type=stats_by_type,
        stats_by_complexity=stats_by_complexity,
        fastest_relative=fastest,
        slowest_relative=slowest,
        highest_quality=highest_quality,
        riskiest=riskiest,
    )
