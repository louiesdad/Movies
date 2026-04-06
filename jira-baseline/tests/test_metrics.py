"""Tests for metrics.py — bucket aggregation."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from datetime import datetime
from models import (
    NormalizedTicket, NormalizedType, Size, Area, Confidence,
    Outcome, ExclusionReason, BucketKey,
)
from metrics import compute_bucket_metrics, build_summary


def _make_normalized(
    key="T-1", ntype=NormalizedType.STORY, size=Size.MEDIUM,
    area=Area.BACKEND, cycle=5.0, lead=8.0, backlog=3.0,
    has_bug=False, has_rework=False, included=True,
    outcome=Outcome.COMPLETED_CLEAN,
):
    return NormalizedTicket(
        key=key, project="TEST",
        normalized_type=ntype, size=size,
        size_confidence=Confidence.HIGH,
        area=area, area_confidence=Confidence.HIGH,
        created_at=datetime(2025, 1, 1),
        started_at=datetime(2025, 1, 3),
        resolved_at=datetime(2025, 1, 8),
        lead_time_days=lead, cycle_time_days=cycle,
        backlog_wait_days=backlog,
        has_bug=has_bug, has_rework=has_rework,
        rework_confidence=Confidence.HIGH if has_rework else None,
        is_duplicate=False, is_epic=False,
        status_mapping_confidence=Confidence.HIGH,
        included_in_baseline=included,
        exclusion_reason=None if included else ExclusionReason.UNRESOLVED,
        outcome=outcome,
        raw_summary="test", raw_type="Story", raw_status="Done",
    )


class TestBucketMetrics(unittest.TestCase):

    def test_single_bucket(self):
        tickets = [
            _make_normalized(key=f"T-{i}", cycle=float(i+1))
            for i in range(5)
        ]
        buckets = compute_bucket_metrics(tickets)
        self.assertEqual(len(buckets), 1)
        b = buckets[0]
        self.assertEqual(b.sample_size, 5)
        self.assertEqual(b.median_cycle_time_days, 3.0)
        self.assertEqual(b.bug_rate, 0.0)
        self.assertEqual(b.clean_completion_rate, 1.0)

    def test_multiple_buckets(self):
        tickets = [
            _make_normalized(key="T-1", ntype=NormalizedType.BUG,
                             size=Size.SMALL, area=Area.FRONTEND),
            _make_normalized(key="T-2", ntype=NormalizedType.STORY,
                             size=Size.MEDIUM, area=Area.BACKEND),
        ]
        buckets = compute_bucket_metrics(tickets)
        self.assertEqual(len(buckets), 2)

    def test_excluded_tickets_not_in_buckets(self):
        tickets = [
            _make_normalized(key="T-1", included=True),
            _make_normalized(key="T-2", included=False),
        ]
        buckets = compute_bucket_metrics(tickets)
        total = sum(b.sample_size for b in buckets)
        self.assertEqual(total, 1)

    def test_bug_and_rework_rates(self):
        tickets = [
            _make_normalized(key="T-1", has_bug=True,
                             outcome=Outcome.COMPLETED_WITH_BUG),
            _make_normalized(key="T-2", has_rework=True,
                             outcome=Outcome.COMPLETED_WITH_REWORK),
            _make_normalized(key="T-3"),
            _make_normalized(key="T-4"),
        ]
        buckets = compute_bucket_metrics(tickets)
        b = buckets[0]
        self.assertAlmostEqual(b.bug_rate, 0.25)
        self.assertAlmostEqual(b.rework_rate, 0.25)
        self.assertAlmostEqual(b.clean_completion_rate, 0.5)

    def test_confidence_levels(self):
        # Low: <5 samples
        tickets = [_make_normalized(key=f"T-{i}") for i in range(3)]
        buckets = compute_bucket_metrics(tickets)
        self.assertEqual(buckets[0].baseline_confidence, Confidence.LOW)

        # Medium: 8-19
        tickets = [_make_normalized(key=f"T-{i}") for i in range(10)]
        buckets = compute_bucket_metrics(tickets)
        self.assertEqual(buckets[0].baseline_confidence, Confidence.MEDIUM)

        # High: >=20
        tickets = [_make_normalized(key=f"T-{i}") for i in range(25)]
        buckets = compute_bucket_metrics(tickets)
        self.assertEqual(buckets[0].baseline_confidence, Confidence.HIGH)

    def test_p75_calculation(self):
        tickets = [
            _make_normalized(key=f"T-{i}", cycle=float(i+1))
            for i in range(4)
        ]
        buckets = compute_bucket_metrics(tickets)
        # Cycle times: 1, 2, 3, 4. P75 should be ~3.25
        self.assertAlmostEqual(buckets[0].p75_cycle_time_days, 3.2, places=0)

    def test_empty_input(self):
        buckets = compute_bucket_metrics([])
        self.assertEqual(len(buckets), 0)


class TestBuildSummary(unittest.TestCase):

    def test_summary_counts(self):
        tickets = [
            _make_normalized(key="T-1", included=True),
            _make_normalized(key="T-2", included=True),
            _make_normalized(key="T-3", included=False),
        ]
        buckets = compute_bucket_metrics(tickets)
        summary = build_summary("TEST", tickets, buckets)
        self.assertEqual(summary.total_issues_fetched, 3)
        self.assertEqual(summary.total_included_in_baseline, 2)
        self.assertEqual(summary.total_excluded, 1)

    def test_slow_buckets_sorted(self):
        tickets = [
            _make_normalized(key="T-1", ntype=NormalizedType.BUG,
                             size=Size.SMALL, area=Area.FRONTEND, cycle=2.0),
            _make_normalized(key="T-2", ntype=NormalizedType.STORY,
                             size=Size.LARGE, area=Area.BACKEND, cycle=20.0),
        ]
        buckets = compute_bucket_metrics(tickets)
        summary = build_summary("TEST", tickets, buckets)
        # Slowest first
        self.assertEqual(summary.slow_buckets[0].median_cycle_time_days, 20.0)


if __name__ == "__main__":
    unittest.main()
