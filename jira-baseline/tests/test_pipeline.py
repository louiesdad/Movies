"""Tests for pipeline.py — end-to-end normalization and analysis."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from datetime import datetime, timedelta
from pipeline import normalize_issue, run_analysis
from normalizer import StatusNormalizer
from config import ProjectConfig
from models import (
    JiraIssue, StatusTransition, Phase, NormalizedType,
    Size, Outcome, ExclusionReason, Confidence,
)


def _make_issue(
    key="TEST-1", issue_type="Story", status="Done", resolution="Done",
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
        created=created, resolved=changelog[-1].timestamp if changelog else None,
        assignee="Alice", sprint="Sprint 1",
        changelog=changelog,
    )


class TestNormalizeIssue(unittest.TestCase):

    def setUp(self):
        self.normalizer = StatusNormalizer()
        self.config = ProjectConfig()

    def test_basic_story(self):
        issue = _make_issue()
        ticket = normalize_issue(issue, self.normalizer, self.config)
        self.assertEqual(ticket.normalized_type, NormalizedType.STORY)
        self.assertEqual(ticket.size, Size.MEDIUM)
        self.assertTrue(ticket.included_in_baseline)
        self.assertEqual(ticket.outcome, Outcome.COMPLETED_CLEAN)
        self.assertIsNone(ticket.exclusion_reason)
        self.assertIsNotNone(ticket.cycle_time_days)
        self.assertIsNotNone(ticket.lead_time_days)

    def test_epic_excluded(self):
        issue = _make_issue(issue_type="Epic", points=None)
        ticket = normalize_issue(issue, self.normalizer, self.config)
        self.assertTrue(ticket.is_epic)
        self.assertFalse(ticket.included_in_baseline)
        self.assertEqual(ticket.exclusion_reason, ExclusionReason.EPIC)

    def test_duplicate_excluded(self):
        issue = _make_issue(resolution="Duplicate")
        ticket = normalize_issue(issue, self.normalizer, self.config)
        self.assertTrue(ticket.is_duplicate)
        self.assertFalse(ticket.included_in_baseline)
        self.assertEqual(ticket.exclusion_reason, ExclusionReason.DUPLICATE)

    def test_unresolved_excluded(self):
        created = datetime(2025, 3, 1)
        changelog = [
            StatusTransition(
                created + timedelta(days=1), "Backlog", "In Progress",
                Phase.BACKLOG, Phase.ACTIVE),
        ]
        issue = JiraIssue(
            key="TEST-1", project="TEST", issue_type="Story",
            status="In Progress", resolution=None,
            priority="Medium", summary="Unresolved ticket",
            description="Still in progress",
            story_points=5, components=["API"], labels=[],
            acceptance_criteria=["AC1"], subtasks=[], dependencies=[],
            linked_bugs=[], created=created, resolved=None,
            assignee="Alice", sprint=None, changelog=changelog,
        )
        ticket = normalize_issue(issue, self.normalizer, self.config)
        self.assertFalse(ticket.included_in_baseline)
        self.assertEqual(ticket.exclusion_reason, ExclusionReason.UNRESOLVED)
        self.assertEqual(ticket.outcome, Outcome.INCOMPLETE)

    def test_bug_detection(self):
        issue = _make_issue(linked_bugs=["TEST-BUG-1"])
        ticket = normalize_issue(issue, self.normalizer, self.config)
        self.assertTrue(ticket.has_bug)
        self.assertEqual(ticket.outcome, Outcome.COMPLETED_WITH_BUG)

    def test_rework_detection_from_changelog(self):
        created = datetime(2025, 3, 1)
        changelog = [
            StatusTransition(created + timedelta(days=1), "Backlog", "In Progress",
                             Phase.BACKLOG, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=3), "In Progress", "In Review",
                             Phase.ACTIVE, Phase.REVIEW),
            StatusTransition(created + timedelta(days=4), "In Review", "In Progress",
                             Phase.REVIEW, Phase.ACTIVE),  # rework!
            StatusTransition(created + timedelta(days=6), "In Progress", "Done",
                             Phase.ACTIVE, Phase.DONE),
        ]
        issue = _make_issue(changelog=changelog)
        ticket = normalize_issue(issue, self.normalizer, self.config)
        self.assertTrue(ticket.has_rework)
        self.assertEqual(ticket.rework_confidence, Confidence.HIGH)
        self.assertEqual(ticket.outcome, Outcome.COMPLETED_WITH_REWORK)

    def test_bug_takes_precedence_over_rework(self):
        created = datetime(2025, 3, 1)
        changelog = [
            StatusTransition(created + timedelta(days=1), "Backlog", "In Progress",
                             Phase.BACKLOG, Phase.ACTIVE),
            StatusTransition(created + timedelta(days=3), "In Progress", "Done",
                             Phase.ACTIVE, Phase.DONE),
            StatusTransition(created + timedelta(days=4), "Done", "In Progress",
                             Phase.DONE, Phase.ACTIVE),  # rework
            StatusTransition(created + timedelta(days=6), "In Progress", "Done",
                             Phase.ACTIVE, Phase.DONE),
        ]
        issue = _make_issue(changelog=changelog, linked_bugs=["BUG-1"])
        ticket = normalize_issue(issue, self.normalizer, self.config)
        self.assertTrue(ticket.has_bug)
        self.assertTrue(ticket.has_rework)
        self.assertEqual(ticket.outcome, Outcome.COMPLETED_WITH_BUG)

    def test_rework_confidence_null_when_no_rework(self):
        issue = _make_issue()
        ticket = normalize_issue(issue, self.normalizer, self.config)
        self.assertFalse(ticket.has_rework)
        self.assertIsNone(ticket.rework_confidence)

    def test_window_exclusion(self):
        issue = _make_issue(created=datetime(2024, 1, 1))
        ticket = normalize_issue(
            issue, self.normalizer, self.config,
            window_start=datetime(2025, 1, 1))
        self.assertFalse(ticket.included_in_baseline)
        self.assertEqual(ticket.exclusion_reason, ExclusionReason.OUTSIDE_WINDOW)

    def test_size_from_story_points(self):
        for pts, expected in [(2, Size.SMALL), (5, Size.MEDIUM), (13, Size.LARGE)]:
            issue = _make_issue(points=pts)
            ticket = normalize_issue(issue, self.normalizer, self.config)
            self.assertEqual(ticket.size, expected, f"Failed for {pts}")


class TestRunAnalysis(unittest.TestCase):

    def test_basic_analysis(self):
        issues = [
            _make_issue(key="T-1", points=2, components=["API"]),
            _make_issue(key="T-2", points=5, components=["API"]),
            _make_issue(key="T-3", points=13, components=["Web UI"]),
            _make_issue(key="T-4", issue_type="Bug", points=3,
                        components=["API"]),
        ]
        tickets, buckets, summary = run_analysis(issues, "TEST")
        self.assertEqual(len(tickets), 4)
        self.assertEqual(summary.total_included_in_baseline, 4)
        self.assertTrue(len(buckets) > 0)

    def test_epic_excluded_from_buckets(self):
        issues = [
            _make_issue(key="T-1", points=5, components=["API"]),
            _make_issue(key="T-2", issue_type="Epic", points=None,
                        components=["API"]),
        ]
        tickets, buckets, summary = run_analysis(issues, "TEST")
        self.assertEqual(summary.total_included_in_baseline, 1)
        self.assertEqual(summary.total_excluded, 1)
        # Bucket should only have the story, not the epic
        total_in_buckets = sum(b.sample_size for b in buckets)
        self.assertEqual(total_in_buckets, 1)

    def test_reproducibility(self):
        issues = [_make_issue(key=f"T-{i}", points=3) for i in range(10)]
        _, b1, s1 = run_analysis(issues, "TEST")
        _, b2, s2 = run_analysis(issues, "TEST")
        self.assertEqual(len(b1), len(b2))
        self.assertEqual(s1.total_included_in_baseline,
                         s2.total_included_in_baseline)


if __name__ == "__main__":
    unittest.main()
