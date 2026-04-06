"""Tests for normalizer.py — type and status normalization."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from normalizer import normalize_type, is_epic_type, StatusNormalizer
from models import NormalizedType, Phase


class TestTypeNormalization(unittest.TestCase):
    def test_bug_variants(self):
        for raw in ["Bug", "bug", "Defect", "defect", "Incident", "INCIDENT"]:
            self.assertEqual(normalize_type(raw), NormalizedType.BUG, f"Failed for {raw}")

    def test_task_variants(self):
        for raw in ["Task", "Chore", "Maintenance", "Sub-Task", "subtask"]:
            self.assertEqual(normalize_type(raw), NormalizedType.TASK)

    def test_story_variants(self):
        for raw in ["Story", "Feature", "User Story"]:
            self.assertEqual(normalize_type(raw), NormalizedType.STORY)

    def test_spike_variants(self):
        for raw in ["Spike", "Research"]:
            self.assertEqual(normalize_type(raw), NormalizedType.SPIKE)

    def test_epic(self):
        self.assertEqual(normalize_type("Epic"), NormalizedType.OTHER)
        self.assertTrue(is_epic_type("Epic"))
        self.assertTrue(is_epic_type("epic"))
        self.assertFalse(is_epic_type("Story"))

    def test_unknown_type(self):
        self.assertEqual(normalize_type("Custom Widget"), NormalizedType.OTHER)


class TestStatusNormalizer(unittest.TestCase):
    def setUp(self):
        self.normalizer = StatusNormalizer()

    def test_done_statuses(self):
        for raw in ["Done", "Closed", "Resolved", "Deployed", "Verified", "Cancelled"]:
            result = self.normalizer.map(raw)
            self.assertEqual(result.phase, Phase.DONE, f"Failed for {raw}")
            self.assertFalse(result.is_blocked)

    def test_review_statuses(self):
        for raw in ["In Review", "Code Review", "In QA", "Testing", "UAT"]:
            result = self.normalizer.map(raw)
            self.assertEqual(result.phase, Phase.REVIEW, f"Failed for {raw}")

    def test_active_statuses(self):
        for raw in ["In Progress", "In Development", "Coding", "WIP"]:
            result = self.normalizer.map(raw)
            self.assertEqual(result.phase, Phase.ACTIVE, f"Failed for {raw}")

    def test_ready_statuses(self):
        for raw in ["To Do", "Ready for Dev", "Open", "Selected for Development"]:
            result = self.normalizer.map(raw)
            self.assertEqual(result.phase, Phase.READY, f"Failed for {raw}")

    def test_backlog_statuses(self):
        for raw in ["Backlog", "Icebox", "Triage"]:
            result = self.normalizer.map(raw)
            self.assertEqual(result.phase, Phase.BACKLOG, f"Failed for {raw}")

    def test_blocked_modifier(self):
        result = self.normalizer.map("Blocked")
        self.assertTrue(result.is_blocked)

        result = self.normalizer.map("On Hold")
        self.assertTrue(result.is_blocked)

    def test_blocked_compound_statuses(self):
        # "Blocked in QA" should be REVIEW + blocked
        result = self.normalizer.map("Blocked in QA")
        self.assertEqual(result.phase, Phase.REVIEW)
        self.assertTrue(result.is_blocked)

        result = self.normalizer.map("Blocked in Review")
        self.assertEqual(result.phase, Phase.REVIEW)
        self.assertTrue(result.is_blocked)

        result = self.normalizer.map("Blocked in Development")
        self.assertEqual(result.phase, Phase.ACTIVE)
        self.assertTrue(result.is_blocked)

    def test_unknown_status(self):
        result = self.normalizer.map("Totally Custom XYZ")
        self.assertEqual(result.phase, Phase.UNKNOWN)
        self.assertEqual(result.confidence, 0.0)

    def test_manual_overrides(self):
        normalizer = StatusNormalizer(overrides={"baking": "review"})
        result = normalizer.map("Baking")
        self.assertEqual(result.phase, Phase.REVIEW)
        self.assertEqual(result.confidence, 1.0)

    def test_duplicate_detection(self):
        self.assertTrue(self.normalizer.is_duplicate_resolution("Duplicate"))
        self.assertTrue(self.normalizer.is_duplicate_resolution("duplicate"))
        self.assertFalse(self.normalizer.is_duplicate_resolution("Done"))
        self.assertFalse(self.normalizer.is_duplicate_resolution(None))

    def test_caching(self):
        r1 = self.normalizer.map("In Progress")
        r2 = self.normalizer.map("In Progress")
        self.assertIs(r1, r2)  # same object from cache


if __name__ == "__main__":
    unittest.main()
