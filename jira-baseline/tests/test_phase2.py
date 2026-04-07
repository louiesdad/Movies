"""Phase 2 tests — config-driven rework/bug detection, confidence, diagnostics."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import tempfile
import unittest
from datetime import datetime, timedelta

from models import (
    JiraIssue, StatusTransition, Phase, NormalizedType,
    Confidence, Outcome, ExclusionReason,
)
from config import ProjectConfig
from normalizer import StatusNormalizer
from timing import derive_timing
from pipeline import normalize_issue, run_analysis


def _make_issue(
    key="T-1", issue_type="Story", status="Done", resolution="Done",
    points=5, components=None, labels=None, created=None,
    changelog=None, linked_bugs=None, description="A test ticket.",
    acceptance_criteria=None, subtasks=None, dependencies=None,
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
        description=description,
        story_points=points,
        components=components or ["API"],
        labels=labels or [],
        acceptance_criteria=acceptance_criteria or ["AC1"],
        subtasks=subtasks or [],
        dependencies=dependencies or [],
        linked_bugs=linked_bugs or [],
        issue_links=[{"type": "is caused by", "target": b}
                     for b in (linked_bugs or [])],
        created=created,
        resolved=changelog[-1].timestamp if changelog else None,
        assignee="Alice", sprint="Sprint 1",
        changelog=changelog,
    )


class TestConfigDrivenRework(unittest.TestCase):
    """Tests that rework_statuses from config are wired into detection."""

    def test_rework_status_detected_from_config(self):
        """A transition to a configured rework status triggers has_rework."""
        created = datetime(2025, 3, 1)
        changelog = [
            StatusTransition(created + timedelta(days=1), "Backlog", "In Progress",
                             Phase.BACKLOG, Phase.ACTIVE),
            # Transition to "Reopened" — a configured rework status
            StatusTransition(created + timedelta(days=3), "In Progress", "Reopened",
                             Phase.ACTIVE, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=5), "Reopened", "Done",
                             Phase.ACTIVE, Phase.DONE),
        ]
        issue = _make_issue(changelog=changelog)

        config = ProjectConfig(rework_statuses=["reopened", "rework"])
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)

        self.assertTrue(ticket.has_rework)
        self.assertEqual(ticket.rework_confidence, Confidence.HIGH)
        self.assertEqual(ticket.outcome, Outcome.COMPLETED_WITH_REWORK)

    def test_no_rework_without_config_match(self):
        """Normal transitions without rework status should not trigger."""
        issue = _make_issue()
        config = ProjectConfig(rework_statuses=["reopened"])
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)

        self.assertFalse(ticket.has_rework)
        self.assertIsNone(ticket.rework_confidence)

    def test_custom_rework_status(self):
        """Custom rework status like 'redo' works when configured."""
        created = datetime(2025, 3, 1)
        changelog = [
            StatusTransition(created + timedelta(days=1), "Backlog", "In Progress",
                             Phase.BACKLOG, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=3), "In Progress", "Redo",
                             Phase.ACTIVE, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=5), "Redo", "Done",
                             Phase.ACTIVE, Phase.DONE),
        ]
        issue = _make_issue(changelog=changelog)
        config = ProjectConfig(rework_statuses=["redo"])
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)

        self.assertTrue(ticket.has_rework)
        self.assertEqual(ticket.rework_confidence, Confidence.HIGH)


class TestReworkConfidenceLevels(unittest.TestCase):
    """Tests that rework confidence matches the signal source."""

    def test_bug_only_rework_gets_medium_confidence(self):
        """Linked bug without backward transition → MEDIUM confidence."""
        issue = _make_issue(linked_bugs=["BUG-1"])
        config = ProjectConfig()
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)
        self.assertTrue(ticket.has_rework)
        self.assertEqual(ticket.rework_confidence, Confidence.MEDIUM)

    def test_backward_transition_rework_gets_high_confidence(self):
        """Backward changelog transition → HIGH confidence."""
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
        self.assertTrue(ticket.has_rework)
        self.assertEqual(ticket.rework_confidence, Confidence.HIGH)

    def test_both_bug_and_transition_gets_high_confidence(self):
        """Both linked bug AND backward transition → HIGH (strong signal wins)."""
        created = datetime(2025, 3, 1)
        changelog = [
            StatusTransition(created + timedelta(days=1), "Backlog", "In Progress",
                             Phase.BACKLOG, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=3), "In Progress", "Done",
                             Phase.ACTIVE, Phase.DONE),
            StatusTransition(created + timedelta(days=4), "Done", "In Progress",
                             Phase.DONE, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=6), "In Progress", "Done",
                             Phase.ACTIVE, Phase.DONE),
        ]
        issue = _make_issue(changelog=changelog, linked_bugs=["BUG-1"])
        config = ProjectConfig()
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)
        self.assertTrue(ticket.has_rework)
        self.assertEqual(ticket.rework_confidence, Confidence.HIGH)


class TestConfigDrivenDoneStatuses(unittest.TestCase):
    """Tests that done_statuses from config are injected into normalizer."""

    def test_custom_done_status(self):
        """A custom done status like 'shipped' maps to DONE phase."""
        config = ProjectConfig(done_statuses=["shipped", "launched"])
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        result = normalizer.map("Launched")
        # "launched" is not in the default keyword rules but is injected
        # via extra_done_statuses
        self.assertEqual(result.phase, Phase.DONE)

    def test_default_done_statuses_still_work(self):
        config = ProjectConfig()
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        for status in ["Done", "Closed", "Resolved"]:
            result = normalizer.map(status)
            self.assertEqual(result.phase, Phase.DONE, f"Failed for {status}")


class TestTimingReworkStatus(unittest.TestCase):
    """Tests that timing.derive_timing respects rework_statuses param."""

    def test_rework_status_flag(self):
        created = datetime(2025, 1, 1)
        changelog = [
            StatusTransition(created + timedelta(days=1), "Backlog", "In Progress",
                             Phase.BACKLOG, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=3), "In Progress", "Reopened",
                             Phase.ACTIVE, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=5), "Reopened", "Done",
                             Phase.ACTIVE, Phase.DONE),
        ]
        result = derive_timing(created, changelog, rework_statuses=["reopened"])
        self.assertTrue(result.has_rework_status)

    def test_no_rework_status_without_config(self):
        created = datetime(2025, 1, 1)
        changelog = [
            StatusTransition(created + timedelta(days=1), "Backlog", "In Progress",
                             Phase.BACKLOG, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=5), "In Progress", "Done",
                             Phase.ACTIVE, Phase.DONE),
        ]
        result = derive_timing(created, changelog, rework_statuses=["reopened"])
        self.assertFalse(result.has_rework_status)
        self.assertFalse(result.has_rework_transition)


class TestRefinedConfidence(unittest.TestCase):
    """Tests that bucket confidence factors in timing quality and status quality."""

    def test_low_confidence_with_poor_status_mapping(self):
        """Bucket with many low-confidence status mappings gets lower confidence."""
        from models import NormalizedTicket, Size, Area, Outcome
        from metrics import compute_bucket_metrics

        def _ticket(i, status_conf=Confidence.HIGH):
            return NormalizedTicket(
                key=f"T-{i}", project="TEST",
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
                status_mapping_confidence=status_conf,
                included_in_baseline=True, exclusion_reason=None,
                outcome=Outcome.COMPLETED_CLEAN,
                raw_summary="test", raw_type="Story", raw_status="Done",
            )

        # 25 tickets with HIGH status confidence → HIGH bucket confidence
        tickets_good = [_ticket(i, Confidence.HIGH) for i in range(25)]
        buckets = compute_bucket_metrics(tickets_good)
        self.assertEqual(buckets[0].baseline_confidence, Confidence.HIGH)

        # 25 tickets with LOW status confidence → not HIGH
        tickets_bad = [_ticket(i, Confidence.LOW) for i in range(25)]
        buckets_bad = compute_bucket_metrics(tickets_bad)
        self.assertNotEqual(buckets_bad[0].baseline_confidence, Confidence.HIGH)


class TestRankedExport(unittest.TestCase):
    """Tests that ranked_slow_buckets.json is generated."""

    def test_ranked_file_exists(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                f"python3 main.py analyze --project PAY --tickets 20 --output {tmpdir}",
                shell=True, capture_output=True, text=True, cwd=os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))))
            self.assertEqual(result.returncode, 0, result.stderr)
            ranked_path = os.path.join(tmpdir, "ranked_slow_buckets.json")
            self.assertTrue(os.path.exists(ranked_path))
            with open(ranked_path) as f:
                data = json.load(f)
            self.assertIsInstance(data, list)
            # Should be sorted by median_cycle_time descending
            cycle_times = [b["median_cycle_time_days"] for b in data
                           if b["median_cycle_time_days"] is not None]
            self.assertEqual(cycle_times, sorted(cycle_times, reverse=True))


class TestInspectChangelog(unittest.TestCase):
    """Tests that inspect-ticket shows changelog diagnostics."""

    def test_changelog_displayed(self):
        import subprocess
        result = subprocess.run(
            "python3 main.py inspect-ticket --ticket PAY-5",
            shell=True, capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CHANGELOG", result.stdout)
        self.assertIn("CLASSIFICATION INPUTS", result.stdout)
        self.assertIn("Components:", result.stdout)


if __name__ == "__main__":
    unittest.main()
