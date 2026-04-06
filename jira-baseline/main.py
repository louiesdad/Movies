#!/usr/bin/env python3
"""
Jira Baseline Analytics V1 — CLI entrypoint.

Usage:
    python main.py analyze --project PAY
    python main.py analyze --project PAY --since 2025-01-01 --output ./out
    python main.py analyze --project PAY --config ./project_rules.yaml
    python main.py inspect-ticket --project PAY --ticket PAY-123
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Optional

from config import load_config
from jira_client import SampleJiraClient
from pipeline import run_analysis
from export import (
    export_tickets_jsonl,
    export_buckets_json,
    export_summary_json,
    export_buckets_csv,
)
from models import Confidence, Outcome


BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"


def _conf_color(c: Confidence) -> str:
    if c == Confidence.HIGH:
        return GREEN
    elif c == Confidence.MEDIUM:
        return YELLOW
    return RED


def _parse_date(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        print(f"Invalid date format: {s} (use YYYY-MM-DD)")
        sys.exit(1)


def cmd_analyze(args):
    """Run baseline analysis on a project."""
    config = load_config(args.config) if args.config else None
    client = SampleJiraClient()

    window_start = _parse_date(args.since) if args.since else None
    window_end = _parse_date(args.until) if args.until else None

    print(f"\n{BOLD}Fetching issues for {args.project}...{RESET}")
    issues = client.fetch_issues(
        args.project, since=window_start, until=window_end,
        count=args.tickets,
    )
    print(f"  Fetched {len(issues)} issues")

    print(f"{BOLD}Running analysis...{RESET}")
    tickets, bucket_metrics, summary = run_analysis(
        issues, args.project, config, window_start, window_end,
    )

    # Print summary to terminal
    _print_summary(summary, bucket_metrics)

    # Export files
    output_dir = args.output or "."
    os.makedirs(output_dir, exist_ok=True)

    tickets_path = os.path.join(output_dir, "tickets_normalized.jsonl")
    buckets_path = os.path.join(output_dir, "bucket_baselines.json")
    summary_path = os.path.join(output_dir, "summary.json")

    export_tickets_jsonl(tickets, tickets_path)
    export_buckets_json(bucket_metrics, buckets_path)
    export_summary_json(summary, summary_path)

    if args.csv:
        csv_path = os.path.join(output_dir, "bucket_baselines.csv")
        export_buckets_csv(bucket_metrics, csv_path)
        print(f"  {DIM}Exported: {csv_path}{RESET}")

    print(f"\n{BOLD}Exports:{RESET}")
    print(f"  {tickets_path}")
    print(f"  {buckets_path}")
    print(f"  {summary_path}")


def _print_summary(summary, bucket_metrics):
    """Print human-readable summary to terminal."""
    s = summary
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  BASELINE ANALYSIS: {s.project_key}{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")
    print(f"  Issues fetched:    {s.total_issues_fetched}")
    print(f"  In baseline:       {s.total_included_in_baseline}")
    print(f"  Excluded:          {s.total_excluded}")
    if s.exclusion_breakdown:
        for reason, count in sorted(s.exclusion_breakdown.items()):
            print(f"    {reason}: {count}")
    print(f"  Buckets:           {s.bucket_count}")
    print(f"  High-confidence:   {s.high_confidence_buckets}")

    if bucket_metrics:
        print(f"\n{BOLD}  BUCKET BASELINES{RESET}")
        print(f"  {'Bucket':<35} {'N':>4} {'Med Cyc':>8} {'P75':>6} "
              f"{'Bug%':>6} {'Rwk%':>6} {'Conf':<6}")
        print(f"  {'─'*35} {'─'*4} {'─'*8} {'─'*6} {'─'*6} {'─'*6} {'─'*6}")
        for b in sorted(bucket_metrics,
                        key=lambda x: x.median_cycle_time_days or 0,
                        reverse=True):
            label = str(b.bucket)
            cyc = f"{b.median_cycle_time_days:.1f}d" if b.median_cycle_time_days else "N/A"
            p75 = f"{b.p75_cycle_time_days:.1f}d" if b.p75_cycle_time_days else "N/A"
            bug = f"{b.bug_rate:.0%}"
            rwk = f"{b.rework_rate:.0%}"
            conf_color = _conf_color(b.baseline_confidence)
            conf = f"{conf_color}{b.baseline_confidence.value}{RESET}"
            print(f"  {label:<35} {b.sample_size:>4} {cyc:>8} {p75:>6} "
                  f"{bug:>6} {rwk:>6} {conf}")

    if s.slow_buckets:
        print(f"\n{BOLD}  SLOWEST BUCKETS{RESET}")
        for b in s.slow_buckets[:5]:
            print(f"    {str(b.bucket):<35} median {b.median_cycle_time_days:.1f}d")

    if s.quality_hotspots:
        hotspots = [h for h in s.quality_hotspots
                    if h.bug_rate + h.rework_rate > 0]
        if hotspots:
            print(f"\n{BOLD}  QUALITY HOTSPOTS{RESET}")
            for b in hotspots[:5]:
                print(f"    {str(b.bucket):<35} bug={b.bug_rate:.0%} rework={b.rework_rate:.0%}")

    print()


def cmd_inspect(args):
    """Deep-dive on a single ticket."""
    config = load_config(args.config) if args.config else None
    client = SampleJiraClient()

    # Parse ticket key
    parts = args.ticket.rsplit("-", 1)
    if len(parts) != 2:
        print(f"Invalid ticket key: {args.ticket}")
        sys.exit(1)
    proj_key = parts[0]
    try:
        ticket_num = int(parts[1])
    except ValueError:
        print(f"Invalid ticket number: {parts[1]} (must be an integer)")
        sys.exit(1)
    if ticket_num < 1:
        print(f"Invalid ticket number: {ticket_num} (must be >= 1)")
        sys.exit(1)

    issues = client.fetch_issues(proj_key, count=args.tickets)
    matching = [i for i in issues if i.key == args.ticket]
    if not matching:
        print(f"Ticket {args.ticket} not found in {len(issues)} fetched issues")
        sys.exit(1)

    from pipeline import normalize_issue
    from normalizer import StatusNormalizer
    normalizer = StatusNormalizer(
        overrides=config.status_overrides if config else None)
    cfg = config or __import__('config').ProjectConfig()
    ticket = normalize_issue(matching[0], normalizer, cfg)

    print(f"\n{BOLD}TICKET: {ticket.key}{RESET}")
    print(f"  Summary:      {ticket.raw_summary}")
    print(f"  Type:         {ticket.raw_type} → {ticket.normalized_type.value}")
    print(f"  Status:       {ticket.raw_status}")
    print(f"  Size:         {ticket.size.value} (confidence: {ticket.size_confidence.value})")
    print(f"  Area:         {ticket.area.value} (confidence: {ticket.area_confidence.value})")
    print(f"  Bucket:       {ticket.normalized_type.value} / {ticket.size.value} / {ticket.area.value}")
    print(f"  Created:      {ticket.created_at.strftime('%Y-%m-%d')}")
    print(f"  Started:      {ticket.started_at.strftime('%Y-%m-%d') if ticket.started_at else 'N/A'}")
    print(f"  Resolved:     {ticket.resolved_at.strftime('%Y-%m-%d') if ticket.resolved_at else 'N/A'}")
    print(f"  Cycle time:   {ticket.cycle_time_days}d" if ticket.cycle_time_days is not None else "  Cycle time:   N/A")
    print(f"  Lead time:    {ticket.lead_time_days}d" if ticket.lead_time_days is not None else "  Lead time:    N/A")
    print(f"  Backlog wait: {ticket.backlog_wait_days}d" if ticket.backlog_wait_days is not None else "  Backlog wait: N/A")
    print(f"  Has bug:      {ticket.has_bug}")
    print(f"  Has rework:   {ticket.has_rework}" +
          (f" (confidence: {ticket.rework_confidence.value})" if ticket.rework_confidence else ""))
    print(f"  Outcome:      {ticket.outcome.value}")
    print(f"  In baseline:  {ticket.included_in_baseline}")
    if ticket.exclusion_reason:
        print(f"  Excluded:     {ticket.exclusion_reason.value}")
    print(f"  Is epic:      {ticket.is_epic}")
    print(f"  Is duplicate: {ticket.is_duplicate}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Jira Baseline Analytics V1"
    )
    subparsers = parser.add_subparsers(dest="command")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Run baseline analysis")
    analyze_parser.add_argument("--project", "-p", required=True,
                                help="Jira project key (e.g., PAY)")
    analyze_parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    analyze_parser.add_argument("--until", help="End date (YYYY-MM-DD)")
    analyze_parser.add_argument("--output", "-o", help="Output directory")
    analyze_parser.add_argument("--config", "-c", help="YAML config file path")
    analyze_parser.add_argument("--tickets", "-n", type=int, default=50,
                                help="Number of sample tickets (default: 50)")
    analyze_parser.add_argument("--csv", action="store_true",
                                help="Also export bucket baselines as CSV")

    # inspect-ticket command
    inspect_parser = subparsers.add_parser("inspect-ticket",
                                            help="Deep-dive on a single ticket")
    inspect_parser.add_argument("--ticket", "-t", required=True,
                                help="Ticket key (e.g., PAY-123)")
    inspect_parser.add_argument("--config", "-c", help="YAML config file path")
    inspect_parser.add_argument("--tickets", "-n", type=int, default=50,
                                help="Number of sample tickets (default: 50)")

    args = parser.parse_args()

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "inspect-ticket":
        cmd_inspect(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
