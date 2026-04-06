"""Tests for timing.py — changelog-driven timing derivation."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from datetime import datetime, timedelta
from timing import derive_timing
from models import StatusTransition, Phase, Confidence


class TestTimingDerivation(unittest.TestCase):

    def _transition(self, days_offset, from_phase, to_phase,
                     from_status="X", to_status="Y"):
        base = datetime(2025, 1, 1)
        return StatusTransition(
            timestamp=base + timedelta(days=days_offset),
            from_status=from_status,
            to_status=to_status,
            from_phase=from_phase,
            to_phase=to_phase,
        )

    def test_full_changelog(self):
        created = datetime(2025, 1, 1)
        changelog = [
            self._transition(2, Phase.BACKLOG, Phase.ACTIVE),
            self._transition(5, Phase.ACTIVE, Phase.REVIEW),
            self._transition(7, Phase.REVIEW, Phase.DONE),
        ]
        result = derive_timing(created, changelog)
        self.assertAlmostEqual(result.lead_time_days, 7.0, places=1)
        self.assertAlmostEqual(result.cycle_time_days, 5.0, places=1)
        self.assertAlmostEqual(result.backlog_wait_days, 2.0, places=1)
        self.assertEqual(result.confidence, Confidence.HIGH)
        self.assertFalse(result.has_rework_transition)

    def test_rework_detection(self):
        created = datetime(2025, 1, 1)
        changelog = [
            self._transition(1, Phase.BACKLOG, Phase.ACTIVE),
            self._transition(3, Phase.ACTIVE, Phase.REVIEW),
            self._transition(4, Phase.REVIEW, Phase.ACTIVE),  # rework!
            self._transition(6, Phase.ACTIVE, Phase.REVIEW),
            self._transition(8, Phase.REVIEW, Phase.DONE),
        ]
        result = derive_timing(created, changelog)
        self.assertTrue(result.has_rework_transition)
        self.assertAlmostEqual(result.cycle_time_days, 7.0, places=1)

    def test_rework_from_done_to_active(self):
        created = datetime(2025, 1, 1)
        changelog = [
            self._transition(1, Phase.BACKLOG, Phase.ACTIVE),
            self._transition(3, Phase.ACTIVE, Phase.DONE),
            self._transition(5, Phase.DONE, Phase.ACTIVE),  # reopened!
            self._transition(7, Phase.ACTIVE, Phase.DONE),
        ]
        result = derive_timing(created, changelog)
        self.assertTrue(result.has_rework_transition)
        # resolved_at should be first transition to DONE (day 3)
        self.assertAlmostEqual(result.cycle_time_days, 2.0, places=1)

    def test_no_changelog_fallback(self):
        created = datetime(2025, 1, 1)
        resolved_static = datetime(2025, 1, 10)
        result = derive_timing(created, [], resolved_static)
        self.assertAlmostEqual(result.lead_time_days, 9.0, places=1)
        self.assertIsNone(result.cycle_time_days)  # no start detected
        self.assertEqual(result.confidence, Confidence.LOW)

    def test_no_resolved(self):
        created = datetime(2025, 1, 1)
        changelog = [
            self._transition(2, Phase.BACKLOG, Phase.ACTIVE),
        ]
        result = derive_timing(created, changelog)
        self.assertIsNone(result.resolved_at)
        self.assertIsNone(result.lead_time_days)
        self.assertIsNone(result.cycle_time_days)
        self.assertAlmostEqual(result.backlog_wait_days, 2.0, places=1)

    def test_empty_changelog_no_fallback(self):
        created = datetime(2025, 1, 1)
        result = derive_timing(created, [])
        self.assertIsNone(result.resolved_at)
        self.assertEqual(result.confidence, Confidence.LOW)

    def test_direct_to_done(self):
        """Ticket goes directly from backlog to done (no active phase)."""
        created = datetime(2025, 1, 1)
        changelog = [
            self._transition(3, Phase.BACKLOG, Phase.DONE),
        ]
        result = derive_timing(created, changelog)
        self.assertAlmostEqual(result.lead_time_days, 3.0, places=1)
        self.assertIsNone(result.cycle_time_days)  # no start
        self.assertEqual(result.confidence, Confidence.MEDIUM)

    def test_zero_cycle_time(self):
        """Started and resolved at the same moment."""
        created = datetime(2025, 1, 1)
        changelog = [
            self._transition(0, Phase.BACKLOG, Phase.ACTIVE),
            self._transition(0, Phase.ACTIVE, Phase.DONE),
        ]
        result = derive_timing(created, changelog)
        self.assertAlmostEqual(result.cycle_time_days, 0.0, places=1)


if __name__ == "__main__":
    unittest.main()
