"""Tests for export.py — JSON/JSONL/CSV output."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import tempfile
import unittest
from datetime import datetime
from models import (
    NormalizedTicket, BucketMetrics, AnalysisSummary,
    NormalizedType, Size, Area, Confidence, Outcome,
    ExclusionReason, BucketKey,
)
from export import (
    export_tickets_jsonl, export_buckets_json,
    export_summary_json, export_buckets_csv,
)


def _sample_ticket():
    return NormalizedTicket(
        key="T-1", project="TEST",
        normalized_type=NormalizedType.STORY, size=Size.MEDIUM,
        size_confidence=Confidence.HIGH,
        area=Area.BACKEND, area_confidence=Confidence.HIGH,
        created_at=datetime(2025, 1, 1),
        started_at=datetime(2025, 1, 3),
        resolved_at=datetime(2025, 1, 8),
        lead_time_days=7.0, cycle_time_days=5.0,
        backlog_wait_days=2.0,
        has_bug=False, has_rework=False, rework_confidence=None,
        is_duplicate=False, is_epic=False,
        status_mapping_confidence=Confidence.HIGH,
        included_in_baseline=True, exclusion_reason=None,
        outcome=Outcome.COMPLETED_CLEAN,
        raw_summary="Test ticket", raw_type="Story", raw_status="Done",
    )


def _sample_bucket():
    return BucketMetrics(
        bucket=BucketKey(NormalizedType.STORY, Size.MEDIUM, Area.BACKEND),
        sample_size=10,
        median_cycle_time_days=5.0,
        p75_cycle_time_days=7.5,
        median_lead_time_days=8.0,
        median_backlog_wait_days=3.0,
        bug_rate=0.1,
        rework_rate=0.2,
        clean_completion_rate=0.7,
        baseline_confidence=Confidence.MEDIUM,
    )


class TestExportJsonl(unittest.TestCase):

    def test_writes_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "tickets.jsonl")
            export_tickets_jsonl([_sample_ticket()], path)
            with open(path) as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 1)
            data = json.loads(lines[0])
            self.assertEqual(data["key"], "T-1")
            self.assertEqual(data["normalized_type"], "story")
            self.assertEqual(data["size"], "medium")
            self.assertEqual(data["outcome"], "completed_clean")
            self.assertIsNone(data["rework_confidence"])

    def test_empty_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "tickets.jsonl")
            export_tickets_jsonl([], path)
            with open(path) as f:
                self.assertEqual(f.read(), "")


class TestExportBucketsJson(unittest.TestCase):

    def test_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "buckets.json")
            export_buckets_json([_sample_bucket()], path)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["bucket"]["type"], "story")
            self.assertEqual(data[0]["sample_size"], 10)


class TestExportSummaryJson(unittest.TestCase):

    def test_writes_valid_json(self):
        summary = AnalysisSummary(
            project_key="TEST",
            analysis_window_start=datetime(2025, 1, 1),
            analysis_window_end=None,
            total_issues_fetched=50,
            total_included_in_baseline=40,
            total_excluded=10,
            exclusion_breakdown={"epic": 5, "duplicate": 3, "unresolved": 2},
            bucket_count=8,
            high_confidence_buckets=3,
            slow_buckets=[_sample_bucket()],
            quality_hotspots=[],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "summary.json")
            export_summary_json(summary, path)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["project_key"], "TEST")
            self.assertEqual(data["total_excluded"], 10)


class TestExportCsv(unittest.TestCase):

    def test_writes_valid_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "buckets.csv")
            export_buckets_csv([_sample_bucket()], path)
            with open(path) as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 2)  # header + 1 row
            self.assertIn("type,size,area", lines[0])
            self.assertIn("story,medium,backend", lines[1])


if __name__ == "__main__":
    unittest.main()
