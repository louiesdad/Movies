"""
Analytics Engine — computes statistics from complexity-scored tickets.

Key concept: COMPLEXITY-ADJUSTED CYCLE TIME
  Raw pace = cycle_time / story_points  (days per point)
  Adjusted pace = cycle_time / complexity_score  (days per complexity unit)

  This lets you compare: "Was a 2-week complex migration actually faster,
  relatively speaking, than a 1-day simple bug fix?"

  A lower adjusted pace means better throughput per unit of real difficulty.
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
    adjusted_pace: Optional[float]           # cycle_time / complexity (days per unit)
    backlog_wait_days: Optional[float]       # lead_time - cycle_time
    backlog_wait_pct: Optional[float]        # % of lead time spent waiting in backlog
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
    cycle_time_stddev: float
    # Lead time
    avg_lead_time: float
    min_lead_time: float
    max_lead_time: float
    # Defects
    total_defects: int
    avg_defects_per_ticket: float
    min_defects: int
    max_defects: int
    avg_defects_by_category: Dict[str, float]  # complexity category -> avg defects
    defect_severity_breakdown: Dict[str, int]  # severity -> total count
    # Quality
    defect_free_rate: float   # % of tickets with zero defects
    critical_defect_rate: float  # % of completed tickets that had a critical defect
    # Velocity
    avg_raw_velocity: float
    avg_adjusted_pace: float
    # By type
    stats_by_type: Dict[str, dict]
    # By complexity category
    stats_by_complexity: Dict[str, dict]
    # By priority
    stats_by_priority: Dict[str, dict]
    # Backlog wait
    avg_backlog_wait: float
    avg_backlog_wait_pct: float              # avg % of lead time spent in backlog
    backlog_is_primary_constraint: bool      # True when avg wait > 50% of avg lead time
    backlog_bottlenecks: List[TicketAnalysis] # tickets where wait > 50% of lead time
    # Top performers and concerns
    fastest_relative: List[TicketAnalysis]
    slowest_relative: List[TicketAnalysis]
    highest_quality: List[TicketAnalysis]    # complex but few defects
    riskiest: List[TicketAnalysis]           # high defects relative to complexity


def _rate_efficiency(adjusted_pace: float, avg_adjusted: float) -> str:
    """Rate a ticket's efficiency relative to the project average.

    Thresholds: <=50% of avg = Exceptional, <=80% = Above Average,
    <=120% = Average, <=150% = Below Average, >150% = Slow.
    """
    if adjusted_pace <= avg_adjusted * 0.5:
        return "Exceptional"
    elif adjusted_pace <= avg_adjusted * 0.8:
        return "Above Average"
    elif adjusted_pace <= avg_adjusted * 1.2:
        return "Average"
    elif adjusted_pace <= avg_adjusted * 1.5:
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
        raw_vel = (ct / ticket.story_points) if (ct is not None and ticket.story_points is not None and ticket.story_points > 0) else None
        adj_pace = (ct / cx.total) if (ct is not None and cx.total > 0) else None
        backlog_wait = (lt - ct) if (lt is not None and ct is not None) else None
        backlog_pct = (backlog_wait / lt * 100) if (backlog_wait is not None and lt is not None and lt > 0) else None

        analyses.append(TicketAnalysis(
            ticket=ticket,
            complexity=cx,
            cycle_time_days=ct,
            lead_time_days=lt,
            defect_count=defect_count,
            unresolved_defect_count=unresolved,
            raw_velocity=raw_vel,
            adjusted_pace=adj_pace,
            backlog_wait_days=round(backlog_wait, 1) if backlog_wait is not None else None,
            backlog_wait_pct=round(backlog_pct, 1) if backlog_pct is not None else None,
            relative_efficiency=None,  # set after computing average
        ))

    # Filter to completed tickets for time-based stats
    completed = [a for a in analyses if a.cycle_time_days is not None]
    if not completed:
        in_progress = sum(1 for a in analyses if a.ticket.status == "In Progress")
        todo = sum(1 for a in analyses if a.ticket.status == "To Do")
        raise ValueError(
            f"No completed tickets found for {project_key}. "
            f"({in_progress} in progress, {todo} in backlog). "
            f"Analysis requires at least one resolved ticket."
        )

    # Compute average adjusted pace for efficiency rating
    adj_paces = [a.adjusted_pace for a in completed if a.adjusted_pace is not None]
    avg_adj_pace = statistics.mean(adj_paces) if adj_paces else 1.0

    # Rate each completed ticket's efficiency
    for a in completed:
        if a.adjusted_pace is not None:
            a.relative_efficiency = _rate_efficiency(
                a.adjusted_pace, avg_adj_pace
            )
        elif a.cycle_time_days is not None:
            # Ticket has cycle time but zero complexity — can't compute pace,
            # so fall back to a raw cycle-time comparison against the average
            avg_ct = statistics.mean(ct for ct in
                [x.cycle_time_days for x in completed] if ct is not None)
            a.relative_efficiency = _rate_efficiency(
                a.cycle_time_days, avg_ct
            )

    cycle_times = [a.cycle_time_days for a in completed]
    lead_times = [a.lead_time_days for a in completed if a.lead_time_days is not None]
    raw_vels = [a.raw_velocity for a in completed if a.raw_velocity is not None]

    # Defect stats — all rates use completed ticket count as denominator
    defect_counts = [a.defect_count for a in completed]
    defect_free = sum(1 for d in defect_counts if d == 0)
    tickets_with_critical = sum(
        1 for a in completed
        if any(d.severity == "critical" for d in a.ticket.linked_defects)
    )
    severity_breakdown = {"critical": 0, "major": 0, "minor": 0, "trivial": 0}
    for a in completed:
        for d in a.ticket.linked_defects:
            severity_breakdown[d.severity] = severity_breakdown.get(d.severity, 0) + 1

    # Stats by ticket type
    stats_by_type: Dict[str, dict] = {}
    for ttype in set(a.ticket.type for a in completed):
        type_items = [a for a in completed if a.ticket.type == ttype]
        type_cts = [a.cycle_time_days for a in type_items]
        type_defects = [a.defect_count for a in type_items]
        type_adj = [a.adjusted_pace for a in type_items
                     if a.adjusted_pace is not None]
        type_complexities = [a.complexity.total for a in type_items]
        type_defect_free = sum(1 for a in type_items if a.defect_count == 0)
        type_has_critical = sum(1 for a in type_items
            if any(d.severity == "critical" for d in a.ticket.linked_defects))
        stats_by_type[ttype] = {
            "count": len(type_items),
            "avg_cycle_time": round(statistics.mean(type_cts), 1),
            "median_cycle_time": round(statistics.median(type_cts), 1),
            "cycle_time_stddev": round(statistics.stdev(type_cts), 1) if len(type_cts) > 1 else 0.0,
            "avg_defects": round(statistics.mean(type_defects), 2),
            "defect_free_rate": round(type_defect_free / len(type_items) * 100, 1),
            "critical_defect_rate": round(type_has_critical / len(type_items) * 100, 1),
            "avg_complexity": round(statistics.mean(type_complexities), 1),
            "avg_adjusted_pace": round(statistics.mean(type_adj), 3) if type_adj else None,
        }

    # Stats by complexity category
    stats_by_complexity: Dict[str, dict] = {}
    for cat in ["Trivial", "Simple", "Moderate", "Complex", "Highly Complex"]:
        cat_items = [a for a in completed if a.complexity.category == cat]
        if not cat_items:
            continue
        cat_cts = [a.cycle_time_days for a in cat_items]
        cat_defects = [a.defect_count for a in cat_items]
        cat_adj = [a.adjusted_pace for a in cat_items
                    if a.adjusted_pace is not None]
        stats_by_complexity[cat] = {
            "count": len(cat_items),
            "avg_cycle_time": round(statistics.mean(cat_cts), 1),
            "median_cycle_time": round(statistics.median(cat_cts), 1),
            "cycle_time_stddev": round(statistics.stdev(cat_cts), 1) if len(cat_cts) > 1 else 0.0,
            "avg_defects": round(statistics.mean(cat_defects), 2),
            "avg_adjusted_pace": round(statistics.mean(cat_adj), 3) if cat_adj else None,
        }

    # Stats by priority
    stats_by_priority: Dict[str, dict] = {}
    for prio in ["Critical", "High", "Medium", "Low"]:
        prio_items = [a for a in completed if a.ticket.priority == prio]
        if not prio_items:
            continue
        prio_cts = [a.cycle_time_days for a in prio_items]
        prio_defects = [a.defect_count for a in prio_items]
        prio_adj = [a.adjusted_pace for a in prio_items if a.adjusted_pace is not None]
        prio_complexities = [a.complexity.total for a in prio_items]
        prio_defect_free = sum(1 for a in prio_items if a.defect_count == 0)
        prio_has_critical = sum(1 for a in prio_items
            if any(d.severity == "critical" for d in a.ticket.linked_defects))
        stats_by_priority[prio] = {
            "count": len(prio_items),
            "avg_cycle_time": round(statistics.mean(prio_cts), 1),
            "median_cycle_time": round(statistics.median(prio_cts), 1),
            "cycle_time_stddev": round(statistics.stdev(prio_cts), 1) if len(prio_cts) > 1 else 0.0,
            "avg_defects": round(statistics.mean(prio_defects), 2),
            "defect_free_rate": round(prio_defect_free / len(prio_items) * 100, 1),
            "critical_defect_rate": round(prio_has_critical / len(prio_items) * 100, 1),
            "avg_complexity": round(statistics.mean(prio_complexities), 1),
            "avg_adjusted_pace": round(statistics.mean(prio_adj), 3) if prio_adj else None,
        }

    # Average defects by complexity category
    avg_defects_by_cat: Dict[str, float] = {}
    for cat, data in stats_by_complexity.items():
        avg_defects_by_cat[cat] = data["avg_defects"]

    # Backlog wait analysis
    backlog_waits = [a.backlog_wait_days for a in completed if a.backlog_wait_days is not None]
    backlog_pcts = [a.backlog_wait_pct for a in completed if a.backlog_wait_pct is not None]
    backlog_bottlenecks = sorted(
        [a for a in completed if a.backlog_wait_pct is not None and a.backlog_wait_pct > 50],
        key=lambda a: a.backlog_wait_pct,
        reverse=True,
    )[:5]

    # Top performers (lowest adjusted pace = fastest relative to complexity)
    sorted_by_vel = sorted(
        [a for a in completed if a.adjusted_pace is not None],
        key=lambda a: a.adjusted_pace,
    )
    fastest = sorted_by_vel[:5]
    slowest = sorted_by_vel[-5:]

    # Highest quality: complex tickets with few defects
    complex_tickets = [a for a in completed if a.complexity.total >= 50]
    highest_quality = sorted(complex_tickets, key=lambda a: a.defect_count)[:5]

    # Riskiest: severity-weighted defect score relative to complexity
    _severity_weight = {"critical": 4.0, "major": 2.0, "minor": 1.0, "trivial": 0.5}
    def _weighted_defect_score(a: TicketAnalysis) -> float:
        return sum(_severity_weight.get(d.severity, 1.0)
                   for d in a.ticket.linked_defects) / max(a.complexity.total, 1)
    riskiest = sorted(completed, key=_weighted_defect_score, reverse=True)[:5]

    return ProjectStats(
        project_key=project_key,
        project_name=project_name,
        total_tickets=len(analyses),
        completed_tickets=len(completed),
        avg_cycle_time=round(statistics.mean(cycle_times), 1),
        min_cycle_time=round(min(cycle_times), 1),
        max_cycle_time=round(max(cycle_times), 1),
        median_cycle_time=round(statistics.median(cycle_times), 1),
        cycle_time_stddev=round(statistics.stdev(cycle_times), 1) if len(cycle_times) > 1 else 0.0,
        avg_lead_time=round(statistics.mean(lead_times), 1) if lead_times else 0,
        min_lead_time=round(min(lead_times), 1) if lead_times else 0,
        max_lead_time=round(max(lead_times), 1) if lead_times else 0,
        total_defects=sum(defect_counts),
        avg_defects_per_ticket=round(statistics.mean(defect_counts), 2),
        min_defects=min(defect_counts),
        max_defects=max(defect_counts),
        avg_defects_by_category=avg_defects_by_cat,
        defect_severity_breakdown=severity_breakdown,
        defect_free_rate=round(defect_free / len(completed) * 100, 1),
        critical_defect_rate=round(tickets_with_critical / len(completed) * 100, 1),
        avg_raw_velocity=round(statistics.mean(raw_vels), 2) if raw_vels else 0,
        avg_adjusted_pace=round(avg_adj_pace, 3),
        avg_backlog_wait=round(statistics.mean(backlog_waits), 1) if backlog_waits else 0,
        avg_backlog_wait_pct=round(statistics.mean(backlog_pcts), 1) if backlog_pcts else 0,
        backlog_is_primary_constraint=(
            statistics.mean(backlog_pcts) > 50 if backlog_pcts else False
        ),
        backlog_bottlenecks=backlog_bottlenecks,
        stats_by_type=stats_by_type,
        stats_by_complexity=stats_by_complexity,
        stats_by_priority=stats_by_priority,
        fastest_relative=fastest,
        slowest_relative=slowest,
        highest_quality=highest_quality,
        riskiest=riskiest,
    )
