#!/usr/bin/env python3
"""
Jira Analytics — Complexity-Adjusted Project Analysis

Analyzes Jira tickets to produce insights that go beyond simple averages.
Uses content-based complexity scoring to enable fair comparisons:
"Was a 2-week migration actually faster than a 1-day bug fix?"

Usage:
    python main.py                    # Interactive project selection
    python main.py --project PAY      # Analyze specific project
    python main.py --all              # Analyze all projects
    python main.py --ticket PAY-7     # Deep-dive on a single ticket
"""

import argparse
import sys
from typing import List

from mock_data import PROJECTS, generate_project_tickets, JiraTicket
from complexity_analyzer import analyze_complexity, ComplexityBreakdown
from analytics_engine import analyze_project, ProjectStats, TicketAnalysis


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"

EFFICIENCY_COLORS = {
    "Exceptional": GREEN,
    "Above Average": GREEN,
    "Average": YELLOW,
    "Below Average": RED,
    "Slow": RED,
}


def hbar(value: float, max_val: float, width: int = 30) -> str:
    """Render a horizontal bar chart."""
    filled = int((value / max(max_val, 0.001)) * width)
    return "█" * filled + "░" * (width - filled)


def section(title: str):
    print(f"\n{BOLD}{'─' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{'─' * 70}{RESET}")


def print_ticket_card(analysis: TicketAnalysis, show_breakdown: bool = False):
    """Print a compact card for a single ticket analysis."""
    t = analysis.ticket
    cx = analysis.complexity
    eff = analysis.relative_efficiency or "N/A"
    color = EFFICIENCY_COLORS.get(eff, RESET)

    ct_str = f"{analysis.cycle_time_days:.1f}d" if analysis.cycle_time_days else "N/A"
    adj_str = (f"{analysis.adjusted_pace:.3f}"
               if analysis.adjusted_pace else "N/A")

    print(f"  {BOLD}{t.key}{RESET}  {t.summary[:55]}")
    print(f"    Type: {t.type:<8}  Points: {t.story_points or '-':<3} "
          f" Complexity: {cx.total:.0f}/100 ({cx.category})")
    print(f"    Cycle: {ct_str:<8}  Defects: {analysis.defect_count:<3} "
          f" Adj.Pace: {adj_str}  "
          f" Efficiency: {color}{eff}{RESET}")

    if show_breakdown:
        print(f"    {DIM}Breakdown: desc={cx.description_score} reqs={cx.requirements_score} "
              f"integ={cx.integration_score} type={cx.type_score} "
              f"scope={cx.scope_score} risk={cx.risk_score}{RESET}")
    print()


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def print_project_report(stats: ProjectStats):
    """Print a full analytics report for a project."""
    section(f"PROJECT REPORT: {stats.project_key} — {stats.project_name}")
    print(f"  Tickets analyzed: {stats.completed_tickets} completed "
          f"/ {stats.total_tickets} total\n")

    # ---- Cycle Time ----
    section("CYCLE TIME (time from start to resolution)")
    print(f"  Average:  {BOLD}{stats.avg_cycle_time:.1f} days{RESET}")
    print(f"  Median:   {stats.median_cycle_time:.1f} days")
    print(f"  Min:      {stats.min_cycle_time:.1f} days")
    print(f"  Max:      {stats.max_cycle_time:.1f} days")
    print(f"  Lead Time (created→resolved): avg {stats.avg_lead_time:.1f}d, "
          f"min {stats.min_lead_time:.1f}d, max {stats.max_lead_time:.1f}d")

    # ---- Backlog Wait ----
    section("BACKLOG WAIT (time from created to started)")
    print(f"  Avg wait:             {BOLD}{stats.avg_backlog_wait:.1f} days{RESET}")
    print(f"  Avg wait as % of lead time: {stats.avg_backlog_wait_pct:.0f}%")
    if stats.backlog_bottlenecks:
        print(f"\n  {BOLD}Bottlenecks{RESET} — tickets where >50% of lead time was backlog wait:")
        for a in stats.backlog_bottlenecks:
            t = a.ticket
            print(f"    {BOLD}{t.key}{RESET}  {t.summary[:45]}")
            print(f"      Lead: {a.lead_time_days:.1f}d  Cycle: {a.cycle_time_days:.1f}d  "
                  f"Wait: {a.backlog_wait_days:.1f}d ({a.backlog_wait_pct:.0f}%)")
    else:
        print(f"\n  {GREEN}+ No bottlenecks — all tickets had wait < 50% of lead time.{RESET}")

    # ---- Defects ----
    section("DEFECT ANALYSIS")
    print(f"  Total defects found:      {stats.total_defects}")
    print(f"  Avg defects per ticket:   {BOLD}{stats.avg_defects_per_ticket:.2f}{RESET}")
    print(f"  Min / Max:                {stats.min_defects} / {stats.max_defects}")
    print(f"  Defect-free rate:         {GREEN}{stats.defect_free_rate:.1f}%{RESET}")
    print(f"  Critical defect rate:     {RED}{stats.critical_defect_rate:.1f}%{RESET} "
          f"of tickets had a critical defect")

    if stats.avg_defects_by_category:
        print(f"\n  {BOLD}Avg defects per ticket by complexity category:{RESET}")
        max_dd = max(stats.avg_defects_by_category.values()) if stats.avg_defects_by_category else 1
        for cat, avg_def in stats.avg_defects_by_category.items():
            bar = hbar(avg_def, max_dd, 20)
            print(f"    {cat:<15} {bar} {avg_def:.2f} defects/ticket")

    # ---- Pace ----
    section("THROUGHPUT ANALYSIS")
    print(f"  {BOLD}Raw pace{RESET} (days per story point):           {stats.avg_raw_velocity:.2f}")
    print(f"  {BOLD}Complexity-adjusted pace{RESET} (days per unit):  {stats.avg_adjusted_pace:.3f}")
    print()
    print(f"  {DIM}Adjusted pace = cycle time / complexity score. Lower = faster.")
    print(f"  This normalizes by content complexity, so you can fairly compare")
    print(f"  a 2-week epic vs a 1-day bug fix.{RESET}")

    # ---- By Type ----
    section("BREAKDOWN BY TICKET TYPE")
    print(f"  {'Type':<10} {'Count':>5} {'Avg Cycle':>10} {'Avg Defects':>12} "
          f"{'Avg Complex':>12} {'Adj Pace':>10}")
    print(f"  {'─'*10} {'─'*5} {'─'*10} {'─'*12} {'─'*12} {'─'*10}")
    for ttype, data in sorted(stats.stats_by_type.items()):
        adj = f"{data['avg_adjusted_pace']:.3f}" if data['avg_adjusted_pace'] else "N/A"
        print(f"  {ttype:<10} {data['count']:>5} {data['avg_cycle_time']:>9.1f}d "
              f"{data['avg_defects']:>12.2f} {data['avg_complexity']:>12.1f} {adj:>10}")

    # ---- By Complexity Category ----
    section("BREAKDOWN BY COMPLEXITY CATEGORY")
    print(f"  {'Category':<16} {'Count':>5} {'Avg Cycle':>10} {'Med Cycle':>10} "
          f"{'Avg Defects':>12} {'Adj Pace':>10}")
    print(f"  {'─'*16} {'─'*5} {'─'*10} {'─'*10} {'─'*12} {'─'*10}")
    for cat in ["Trivial", "Simple", "Moderate", "Complex", "Highly Complex"]:
        if cat not in stats.stats_by_complexity:
            continue
        data = stats.stats_by_complexity[cat]
        adj = f"{data['avg_adjusted_pace']:.3f}" if data['avg_adjusted_pace'] else "N/A"
        print(f"  {cat:<16} {data['count']:>5} {data['avg_cycle_time']:>9.1f}d "
              f"{data['median_cycle_time']:>9.1f}d {data['avg_defects']:>12.2f} {adj:>10}")

    # ---- Key insight ----
    section("KEY INSIGHT: RELATIVE PERFORMANCE")
    print(f"  {BOLD}Complexity-adjusted pace reveals true throughput.{RESET}\n")

    # Compare the fastest complex ticket to the slowest simple ticket
    complex_fast = [a for a in stats.fastest_relative if a.complexity.total >= 50]
    simple_slow = [a for a in stats.slowest_relative if a.complexity.total < 40]

    if complex_fast and simple_slow:
        cf = complex_fast[0]
        ss = simple_slow[0]
        print(f"  Example comparison:")
        print(f"    {GREEN}+ FAST (relative){RESET}: {cf.ticket.key} — "
              f"\"{cf.ticket.summary[:45]}\"")
        print(f"      Complexity: {cf.complexity.total:.0f}  "
              f"Cycle: {cf.cycle_time_days:.1f}d  "
              f"Adj.Pace: {cf.adjusted_pace:.3f}")
        print()
        print(f"    {RED}- SLOW (relative){RESET}: {ss.ticket.key} — "
              f"\"{ss.ticket.summary[:45]}\"")
        print(f"      Complexity: {ss.complexity.total:.0f}  "
              f"Cycle: {ss.cycle_time_days:.1f}d  "
              f"Adj.Pace: {ss.adjusted_pace:.3f}")
        print()
        if cf.adjusted_pace and ss.adjusted_pace:
            ratio = ss.adjusted_pace / cf.adjusted_pace
            print(f"    {BOLD}The complex ticket was {ratio:.1f}x more efficient "
                  f"per unit of complexity.{RESET}")
            print(f"    Despite taking longer in absolute time, it delivered more "
                  f"value per day of effort.")
    else:
        print(f"  {DIM}Not enough variety in complexity levels to show a comparison.")
        print(f"  Need both complex (score >= 50) and simple (score < 40) tickets.{RESET}")

    # ---- Top performers ----
    section("TOP 5 — BEST PACE (complexity-adjusted)")
    for a in stats.fastest_relative:
        print_ticket_card(a)

    section("BOTTOM 5 — WORST PACE (complexity-adjusted)")
    for a in stats.slowest_relative:
        print_ticket_card(a)

    # ---- Quality standouts ----
    section("QUALITY STANDOUTS — Complex tickets with fewest defects")
    for a in stats.highest_quality:
        print_ticket_card(a)

    section("RISK WATCH — Highest severity-weighted defect score vs complexity")
    for a in stats.riskiest:
        print_ticket_card(a)

    # ---- Summary ----
    section("EXECUTIVE SUMMARY")
    crit_str = f"{stats.critical_defect_rate:.0f}% of tickets had a critical defect"
    print(f"""
  {BOLD}{stats.project_name} ({stats.project_key}){RESET}

  {stats.completed_tickets} tickets completed with an average cycle time of
  {stats.avg_cycle_time:.1f} days (median: {stats.median_cycle_time:.1f}d).

  Quality: {stats.defect_free_rate:.0f}% of tickets shipped defect-free.
  Average {stats.avg_defects_per_ticket:.1f} defects per ticket, with
  {crit_str}.

  Complexity-adjusted pace: {stats.avg_adjusted_pace:.3f} days per
  complexity unit — this normalizes for ticket difficulty, enabling fair
  comparison across ticket types and sizes.

  {BOLD}Key takeaway:{RESET} Raw cycle time alone is misleading. A ticket that
  took 2 weeks but scored 80/100 on complexity (adj. pace ~0.18) is
  actually more efficient than a ticket that took 3 days but scored only
  15/100 (adj. pace ~0.20). Use adjusted pace to evaluate team
  throughput fairly.
""")


def print_ticket_deepdive(ticket: JiraTicket):
    """Print a detailed analysis of a single ticket."""
    cx = analyze_complexity(ticket)

    section(f"TICKET DEEP DIVE: {ticket.key}")
    print(f"  Summary:   {ticket.summary}")
    print(f"  Type:      {ticket.type}")
    print(f"  Priority:  {ticket.priority}")
    print(f"  Status:    {ticket.status}")
    print(f"  Assignee:  {ticket.assignee}")
    print(f"  Points:    {ticket.story_points}")
    print(f"  Sprint:    {ticket.sprint or 'N/A'}")
    print(f"  Labels:    {', '.join(ticket.labels) or 'None'}")
    print(f"  Components:{', '.join(ticket.components)}")

    section("TIMING")
    print(f"  Created:   {ticket.created.strftime('%Y-%m-%d')}")
    print(f"  Started:   {ticket.started.strftime('%Y-%m-%d') if ticket.started else 'N/A'}")
    print(f"  Resolved:  {ticket.resolved.strftime('%Y-%m-%d') if ticket.resolved else 'N/A'}")
    ct = ticket.cycle_time_days
    lt = ticket.lead_time_days
    print(f"  Cycle time: {ct:.1f} days" if ct else "  Cycle time: N/A")
    print(f"  Lead time:  {lt:.1f} days" if lt else "  Lead time:  N/A")

    section("COMPLEXITY ANALYSIS")
    print(f"  {BOLD}Overall score: {cx.total:.0f}/100 — {cx.category}{RESET}\n")
    max_component = max(cx.description_score, cx.requirements_score,
                         cx.integration_score, cx.type_score,
                         cx.scope_score, cx.risk_score, 1)
    components = [
        ("Description richness", cx.description_score, 15),
        ("Requirements depth", cx.requirements_score, 15),
        ("Integration scope", cx.integration_score, 15),
        ("Type complexity", cx.type_score, 15),
        ("Team estimate (pts)", cx.scope_score, 25),
        ("Risk indicators", cx.risk_score, 15),
    ]
    for name, score, max_score in components:
        bar = hbar(score, max_score, 25)
        print(f"  {name:<22} {bar} {score:>5.1f} / {max_score}")

    section("DESCRIPTION")
    for line in ticket.description.split("\n"):
        print(f"  {DIM}{line}{RESET}")

    if ticket.acceptance_criteria:
        section(f"ACCEPTANCE CRITERIA ({len(ticket.acceptance_criteria)})")
        for i, ac in enumerate(ticket.acceptance_criteria, 1):
            print(f"  {i}. {ac}")

    if ticket.subtasks:
        section(f"SUBTASKS ({len(ticket.subtasks)})")
        for st in ticket.subtasks:
            print(f"  - {st}")

    if ticket.linked_defects:
        section(f"LINKED DEFECTS ({len(ticket.linked_defects)})")
        for d in ticket.linked_defects:
            status = f"{GREEN}Resolved ({d.resolution_days:.1f}d){RESET}" if d.resolved else f"{RED}Open{RESET}"
            print(f"  {d.key}  [{d.severity.upper()}]  {status}")

    if ct and cx.total > 0:
        adj_pace = ct / cx.total
        section("COMPLEXITY-ADJUSTED PACE")
        print(f"  Adjusted pace: {adj_pace:.3f} days per complexity unit (lower = faster)")
        print(f"  Raw pace:      {ct / (ticket.story_points or 1):.2f} days per story point")
        print()
        if adj_pace < 0.15:
            print(f"  {GREEN}+ This ticket was executed efficiently relative to its complexity.{RESET}")
        elif adj_pace < 0.25:
            print(f"  {YELLOW}~ This ticket was executed at a typical pace for its complexity.{RESET}")
        else:
            print(f"  {RED}- This ticket took longer than expected for its complexity level.{RESET}")


# ---------------------------------------------------------------------------
# Interactive project selector
# ---------------------------------------------------------------------------

def select_projects_interactive() -> List[str]:
    """Interactive menu for project selection."""
    print(f"\n{BOLD}{'═' * 50}{RESET}")
    print(f"{BOLD}{CYAN}  JIRA ANALYTICS — Project Selection{RESET}")
    print(f"{BOLD}{'═' * 50}{RESET}\n")
    print("  Available projects:\n")
    keys = list(PROJECTS.keys())
    for i, key in enumerate(keys, 1):
        proj = PROJECTS[key]
        print(f"    {BOLD}{i}.{RESET} {key} — {proj['name']}")
        print(f"       Components: {', '.join(proj['components'])}")
        print()
    print(f"    {BOLD}{len(keys) + 1}.{RESET} All projects")
    print()

    while True:
        try:
            choice = input(f"  Select project(s) (comma-separated numbers, or 'q' to quit): ").strip()
            if choice.lower() == 'q':
                sys.exit(0)
            nums = [int(x.strip()) for x in choice.split(",")]
            if len(keys) + 1 in nums:
                return keys
            selected = []
            for n in nums:
                if 1 <= n <= len(keys):
                    selected.append(keys[n - 1])
                else:
                    print(f"  Invalid selection: {n}")
                    continue
            if selected:
                return selected
        except (ValueError, EOFError):
            print("  Please enter valid numbers.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Jira Analytics — Complexity-Adjusted Project Analysis"
    )
    parser.add_argument("--project", "-p", type=str,
                         help="Project key (e.g., PAY, MOBX, INFRA)")
    parser.add_argument("--all", "-a", action="store_true",
                         help="Analyze all projects")
    parser.add_argument("--ticket", "-t", type=str,
                         help="Deep-dive on a specific ticket (e.g., PAY-7)")
    parser.add_argument("--tickets", "-n", type=int, default=30,
                         help="Number of mock tickets per project (default: 30)")
    args = parser.parse_args()

    # Single ticket deep-dive
    if args.ticket:
        parts = args.ticket.rsplit("-", 1)
        if len(parts) != 2:
            print(f"Invalid ticket key: {args.ticket}")
            sys.exit(1)
        proj_key = parts[0]
        ticket_num = int(parts[1])
        if proj_key not in PROJECTS:
            print(f"Unknown project: {proj_key}")
            sys.exit(1)
        tickets = generate_project_tickets(proj_key, count=max(ticket_num, args.tickets))
        if ticket_num > len(tickets):
            print(f"Ticket {args.ticket} not found")
            sys.exit(1)
        print_ticket_deepdive(tickets[ticket_num - 1])
        return

    # Determine which projects to analyze
    if args.all:
        selected = list(PROJECTS.keys())
    elif args.project:
        if args.project not in PROJECTS:
            print(f"Unknown project: {args.project}. Available: {', '.join(PROJECTS.keys())}")
            sys.exit(1)
        selected = [args.project]
    else:
        selected = select_projects_interactive()

    # Run analysis for each project
    for proj_key in selected:
        proj = PROJECTS[proj_key]
        tickets = generate_project_tickets(proj_key, count=args.tickets)
        stats = analyze_project(tickets, proj_key, proj["name"])
        print_project_report(stats)


if __name__ == "__main__":
    main()
