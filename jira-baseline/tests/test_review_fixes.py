"""Regression tests for review findings: duplicate status, bug/rework decoupling,
config validation enforcement."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
import subprocess
import unittest
from datetime import datetime, timedelta

from models import (
    JiraIssue, StatusTransition, Phase, Confidence,
    Outcome, ExclusionReason,
)
from config import ProjectConfig
from normalizer import StatusNormalizer
from pipeline import normalize_issue


def _make_issue(
    key="T-1", issue_type="Story", status="Done", resolution="Done",
    points=5, components=None, labels=None, created=None,
    changelog=None, linked_bugs=None, issue_links=None,
    description="A test ticket.",
):
    created = created or datetime(2025, 3, 1)
    if changelog is None:
        started = created + timedelta(days=2)
        resolved = started + timedelta(days=5)
        changelog = [
            StatusTransition(started, "Backlog", "In Progress",
                             Phase.BACKLOG, Phase.ACTIVE),
            StatusTransition(resolved, "In Progress", "Done",
                             Phase.ACTIVE, Phase.DONE),
        ]
    return JiraIssue(
        key=key, project="TEST", issue_type=issue_type,
        status=status, resolution=resolution,
        priority="Medium", summary=f"Test ticket {key}",
        description=description, story_points=points,
        components=components or ["API"], labels=labels or [],
        acceptance_criteria=["AC1"], subtasks=[], dependencies=[],
        linked_bugs=linked_bugs or [],
        issue_links=issue_links or [],
        created=created,
        resolved=changelog[-1].timestamp if changelog else None,
        assignee="Alice", sprint="Sprint 1", changelog=changelog,
    )


class TestDuplicateStatusDetection(unittest.TestCase):
    """Fix #1: status='Duplicate' with resolution=None should be excluded."""

    def test_duplicate_status_excluded(self):
        """Ticket with status='Duplicate' but resolution=None → excluded."""
        issue = _make_issue(status="Duplicate", resolution=None)
        config = ProjectConfig()
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)
        self.assertTrue(ticket.is_duplicate)
        self.assertFalse(ticket.included_in_baseline)
        self.assertEqual(ticket.exclusion_reason, ExclusionReason.DUPLICATE)

    def test_duplicate_resolution_still_works(self):
        """Ticket with resolution='Duplicate' → still excluded."""
        issue = _make_issue(resolution="Duplicate")
        config = ProjectConfig()
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)
        self.assertTrue(ticket.is_duplicate)
        self.assertFalse(ticket.included_in_baseline)

    def test_non_duplicate_not_affected(self):
        """Normal ticket not flagged as duplicate."""
        issue = _make_issue(status="Done", resolution="Done")
        config = ProjectConfig()
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)
        self.assertFalse(ticket.is_duplicate)
        self.assertTrue(ticket.included_in_baseline)


class TestBugReworkDecoupled(unittest.TestCase):
    """Fix #2: bug and rework are independent signals."""

    def test_bug_without_rework(self):
        """Linked bug alone → has_bug=True, has_rework=False."""
        issue = _make_issue(linked_bugs=["BUG-1"])
        config = ProjectConfig()
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)
        self.assertTrue(ticket.has_bug)
        self.assertFalse(ticket.has_rework)
        self.assertIsNone(ticket.rework_confidence)
        self.assertEqual(ticket.outcome, Outcome.COMPLETED_WITH_BUG)

    def test_rework_without_bug(self):
        """Backward transition alone → has_rework=True, has_bug=False."""
        created = datetime(2025, 3, 1)
        changelog = [
            StatusTransition(created + timedelta(days=1), "Backlog", "In Progress",
                             Phase.BACKLOG, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=3), "In Progress", "In Review",
                             Phase.ACTIVE, Phase.REVIEW),
            StatusTransition(created + timedelta(days=4), "In Review", "In Progress",
                             Phase.REVIEW, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=6), "In Progress", "Done",
                             Phase.ACTIVE, Phase.DONE),
        ]
        issue = _make_issue(changelog=changelog)
        config = ProjectConfig()
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)
        self.assertFalse(ticket.has_bug)
        self.assertTrue(ticket.has_rework)
        self.assertEqual(ticket.rework_confidence, Confidence.HIGH)
        self.assertEqual(ticket.outcome, Outcome.COMPLETED_WITH_REWORK)

    def test_combined_bug_rate_rework_rate_cannot_exceed_one_each(self):
        """Bug rate and rework rate are independent — each maxes at 1.0."""
        from metrics import compute_bucket_metrics
        from models import NormalizedTicket, NormalizedType, Size, Area

        def _ticket(key, has_bug, has_rework, outcome):
            return NormalizedTicket(
                key=key, project="TEST",
                normalized_type=NormalizedType.STORY, size=Size.MEDIUM,
                size_confidence=Confidence.HIGH,
                area=Area.BACKEND, area_confidence=Confidence.HIGH,
                created_at=datetime(2025, 1, 1),
                started_at=datetime(2025, 1, 3),
                resolved_at=datetime(2025, 1, 8),
                lead_time_days=7.0, cycle_time_days=5.0,
                backlog_wait_days=2.0,
                has_bug=has_bug, has_rework=has_rework,
                rework_confidence=Confidence.HIGH if has_rework else None,
                is_duplicate=False, is_epic=False,
                status_mapping_confidence=Confidence.HIGH,
                included_in_baseline=True, exclusion_reason=None,
                outcome=outcome,
                raw_summary="test", raw_type="Story", raw_status="Done",
            )

        # 4 tickets: 1 bug-only, 1 rework-only, 1 both, 1 clean
        tickets = [
            _ticket("T-1", True, False, Outcome.COMPLETED_WITH_BUG),
            _ticket("T-2", False, True, Outcome.COMPLETED_WITH_REWORK),
            _ticket("T-3", True, True, Outcome.COMPLETED_WITH_BUG),
            _ticket("T-4", False, False, Outcome.COMPLETED_CLEAN),
        ]
        buckets = compute_bucket_metrics(tickets)
        b = buckets[0]
        # bug_rate = 2/4 = 0.5, rework_rate = 2/4 = 0.5
        self.assertAlmostEqual(b.bug_rate, 0.5)
        self.assertAlmostEqual(b.rework_rate, 0.5)
        # Combined is 1.0, not >1.0
        self.assertLessEqual(b.bug_rate + b.rework_rate, 1.5)  # reasonable bound


class TestConfigValidationEnforced(unittest.TestCase):
    """Fix #3: config validation runs on analyze/inspect, not just validate-config."""

    def test_invalid_config_blocks_analyze(self):
        """analyze with invalid config should exit with error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml",
                                          delete=False) as f:
            f.write("status_overrides:\n  baking: not_a_phase\n")
            path = f.name
        try:
            result = subprocess.run(
                f"python3 main.py analyze --project PAY --config {path} --tickets 5",
                shell=True, capture_output=True, text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("error", result.stdout.lower())
        finally:
            os.unlink(path)

    def test_valid_config_passes_analyze(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml",
                                          delete=False) as f:
            f.write("status_overrides:\n  baking: review\n")
            path = f.name
        try:
            result = subprocess.run(
                f"python3 main.py analyze --project PAY --config {path} --tickets 5 --output /tmp/cfg-test",
                shell=True, capture_output=True, text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            os.unlink(path)

    def test_invalid_override_warns_on_stderr(self):
        """Pipeline should emit warning for invalid status override."""
        from pipeline import run_analysis
        from jira_client import SampleJiraClient
        import io, contextlib

        config = ProjectConfig(status_overrides={"baking": "not_a_phase"})
        client = SampleJiraClient()
        issues = client.fetch_issues("PAY", count=5)

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            run_analysis(issues, "PAY", config)

        self.assertIn("invalid status override", stderr.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
