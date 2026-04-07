"""Phase 3 tests — config validation, area boundary matching, richer summary,
defect_link_types wiring."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import tempfile
import unittest
from datetime import datetime, timedelta

from validate import validate_config
from classifier import classify_area, _match_keywords
from models import (
    Area, Confidence, JiraIssue, StatusTransition, Phase,
    NormalizedType, Outcome,
)
from config import ProjectConfig
from normalizer import StatusNormalizer
from pipeline import normalize_issue, run_analysis


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

class TestConfigValidation(unittest.TestCase):

    def test_valid_config(self):
        raw = {
            "status_overrides": {"baking": "review"},
            "area_rules": {"payments": "backend"},
            "done_statuses": ["done", "shipped"],
        }
        errors, warnings = validate_config(raw)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_invalid_phase(self):
        raw = {"status_overrides": {"baking": "not_a_phase"}}
        errors, warnings = validate_config(raw)
        self.assertTrue(any("invalid phase" in e for e in errors))

    def test_invalid_area(self):
        raw = {"area_rules": {"payments": "not_an_area"}}
        errors, warnings = validate_config(raw)
        self.assertTrue(any("invalid area" in e for e in errors))

    def test_non_dict_status_overrides(self):
        raw = {"status_overrides": ["not", "a", "dict"]}
        errors, warnings = validate_config(raw)
        self.assertTrue(any("must be a mapping" in e for e in errors))

    def test_non_list_rework_statuses(self):
        raw = {"rework_statuses": "not_a_list"}
        errors, warnings = validate_config(raw)
        self.assertTrue(any("must be a list" in e for e in errors))

    def test_empty_list_warning(self):
        raw = {"done_statuses": []}
        errors, warnings = validate_config(raw)
        self.assertEqual(errors, [])
        self.assertTrue(any("empty" in w for w in warnings))

    def test_unknown_key_warning(self):
        raw = {"totally_made_up_key": "value"}
        errors, warnings = validate_config(raw)
        self.assertEqual(errors, [])
        self.assertTrue(any("Unknown config key" in w for w in warnings))

    def test_non_string_list_item(self):
        raw = {"done_statuses": ["done", 123]}
        errors, warnings = validate_config(raw)
        self.assertTrue(any("must be a string" in e for e in errors))

    def test_spaces_in_story_point_field(self):
        raw = {"story_point_field": "story points custom"}
        errors, warnings = validate_config(raw)
        self.assertTrue(any("contains spaces" in w for w in warnings))

    def test_empty_config(self):
        errors, warnings = validate_config({})
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


# ---------------------------------------------------------------------------
# Area boundary matching
# ---------------------------------------------------------------------------

class TestAreaBoundaryMatching(unittest.TestCase):

    def test_ci_does_not_match_specification(self):
        """'ci' should NOT match 'specification' (word boundary)."""
        hits = {}
        _match_keywords("specification review", hits, weight=1)
        self.assertNotIn(Area.INFRA, hits,
                         "'ci' in 'specification' should not match with boundary check")

    def test_ci_matches_ci_pipeline(self):
        """'ci' should match 'ci pipeline' or 'ci/cd'."""
        hits = {}
        _match_keywords("ci pipeline setup", hits, weight=1)
        self.assertIn(Area.INFRA, hits)

    def test_api_does_not_match_capital(self):
        """'api' boundary match should work case-insensitively."""
        hits = {}
        _match_keywords("update the api gateway", hits, weight=1)
        self.assertIn(Area.BACKEND, hits)

    def test_ui_does_not_match_build(self):
        """'ui' should NOT match 'build' — only word boundary."""
        hits = {}
        _match_keywords("build the package", hits, weight=1)
        self.assertNotIn(Area.FRONTEND, hits)

    def test_ios_boundary(self):
        hits = {}
        _match_keywords("fix ios crash", hits, weight=1)
        self.assertIn(Area.MOBILE, hits)

    def test_ml_boundary(self):
        hits = {}
        _match_keywords("train ml model", hits, weight=1)
        self.assertIn(Area.DATA, hits)

    def test_multi_word_keyword(self):
        """Multi-word keywords like 'react native' use substring match."""
        area, conf = classify_area(
            components=["Mobile App"], labels=["mobile"],
            summary="Fix react native navigation bug")
        self.assertEqual(area, Area.MOBILE)


# ---------------------------------------------------------------------------
# Richer summary
# ---------------------------------------------------------------------------

class TestSummaryRecommendations(unittest.TestCase):

    def test_summary_has_recommendations(self):
        from jira_client import SampleJiraClient
        client = SampleJiraClient()
        issues = client.fetch_issues("PAY", count=20)
        _, _, summary = run_analysis(issues, "PAY")
        self.assertIsInstance(summary.recommendations, list)
        self.assertTrue(len(summary.recommendations) > 0)

    def test_summary_has_data_quality(self):
        from jira_client import SampleJiraClient
        client = SampleJiraClient()
        issues = client.fetch_issues("PAY", count=20)
        _, _, summary = run_analysis(issues, "PAY")
        dq = summary.data_quality
        self.assertIn("timing_coverage", dq)
        self.assertIn("status_mapping_quality", dq)
        self.assertIn("size_confidence_quality", dq)
        self.assertIn("included_ratio", dq)
        # All should be 0-1
        for key, val in dq.items():
            self.assertGreaterEqual(val, 0)
            self.assertLessEqual(val, 1)

    def test_summary_json_includes_new_fields(self):
        from jira_client import SampleJiraClient
        from export import export_summary_json
        client = SampleJiraClient()
        issues = client.fetch_issues("PAY", count=20)
        _, _, summary = run_analysis(issues, "PAY")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "summary.json")
            export_summary_json(summary, path)
            with open(path) as f:
                data = json.load(f)
            self.assertIn("data_quality", data)
            self.assertIn("recommendations", data)
            self.assertIsInstance(data["recommendations"], list)


# ---------------------------------------------------------------------------
# defect_link_types wiring
# ---------------------------------------------------------------------------

class TestDefectLinkTypes(unittest.TestCase):

    def _make_issue_with_link(self, link_type="is caused by"):
        created = datetime(2025, 3, 1)
        started = created + timedelta(days=2)
        resolved = started + timedelta(days=5)
        changelog = [
            StatusTransition(started, "Backlog", "In Progress",
                             Phase.BACKLOG, Phase.ACTIVE),
            StatusTransition(resolved, "In Progress", "Done",
                             Phase.ACTIVE, Phase.DONE),
        ]
        return JiraIssue(
            key="T-1", project="TEST", issue_type="Story",
            status="Done", resolution="Done",
            priority="Medium", summary="Test ticket",
            description="A test", story_points=5,
            components=["API"], labels=[],
            acceptance_criteria=["AC1"], subtasks=[],
            dependencies=[], linked_bugs=[],
            issue_links=[{"type": link_type, "target": "BUG-1"}],
            created=created, resolved=resolved,
            assignee="Alice", sprint="Sprint 1",
            changelog=changelog,
        )

    def test_matching_link_type_triggers_bug(self):
        issue = self._make_issue_with_link("is caused by")
        config = ProjectConfig(defect_link_types=["is caused by"])
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)
        self.assertTrue(ticket.has_bug)

    def test_non_matching_link_type_no_bug(self):
        issue = self._make_issue_with_link("relates to")
        config = ProjectConfig(defect_link_types=["is caused by"])
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)
        self.assertFalse(ticket.has_bug)

    def test_empty_defect_link_types_no_bug(self):
        issue = self._make_issue_with_link("is caused by")
        config = ProjectConfig(defect_link_types=[])
        normalizer = StatusNormalizer(extra_done_statuses=config.done_statuses)
        ticket = normalize_issue(issue, normalizer, config)
        self.assertFalse(ticket.has_bug)


# ---------------------------------------------------------------------------
# CLI validate-config
# ---------------------------------------------------------------------------

class TestValidateConfigCLI(unittest.TestCase):

    def test_valid_yaml(self):
        import subprocess
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml",
                                          delete=False) as f:
            f.write("status_overrides:\n  baking: review\n")
            path = f.name
        try:
            result = subprocess.run(
                f"python3 main.py validate-config --config {path}",
                shell=True, capture_output=True, text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("No errors", result.stdout)
        finally:
            os.unlink(path)

    def test_invalid_yaml_phase(self):
        import subprocess
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml",
                                          delete=False) as f:
            f.write("status_overrides:\n  baking: not_a_phase\n")
            path = f.name
        try:
            result = subprocess.run(
                f"python3 main.py validate-config --config {path}",
                shell=True, capture_output=True, text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.assertEqual(result.returncode, 1)
            self.assertIn("ERRORS", result.stdout)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
