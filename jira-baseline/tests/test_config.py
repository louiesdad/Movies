"""Tests for config.py — configuration loading."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
import unittest
from config import load_config, ProjectConfig


class TestConfigDefaults(unittest.TestCase):

    def test_default_config(self):
        config = load_config(None)
        self.assertIsInstance(config, ProjectConfig)
        self.assertEqual(config.status_overrides, {})
        self.assertEqual(config.story_point_field, "story_points")
        self.assertIn("done", config.done_statuses)
        self.assertIn("is caused by", config.defect_link_types)

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_config("/nonexistent/path.yaml")


class TestConfigYaml(unittest.TestCase):

    def _write_yaml(self, content: str) -> str:
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_load_partial_yaml(self):
        """YAML with only some fields should use defaults for the rest."""
        path = self._write_yaml("status_overrides:\n  baking: review\n")
        try:
            config = load_config(path)
            self.assertEqual(config.status_overrides, {"baking": "review"})
            # Defaults should still be populated
            self.assertIn("done", config.done_statuses)
            self.assertIn("is caused by", config.defect_link_types)
        finally:
            os.unlink(path)

    def test_load_empty_yaml(self):
        path = self._write_yaml("")
        try:
            config = load_config(path)
            self.assertIsInstance(config, ProjectConfig)
        finally:
            os.unlink(path)

    def test_load_full_yaml(self):
        path = self._write_yaml(
            "status_overrides:\n  baking: review\n"
            "area_rules:\n  payments: backend\n"
            "story_point_field: custom_points\n"
            "defect_link_types:\n  - blocks\n"
            "rework_statuses:\n  - redo\n"
            "done_statuses:\n  - finished\n"
            "project_timezone: US/Pacific\n"
        )
        try:
            config = load_config(path)
            self.assertEqual(config.status_overrides, {"baking": "review"})
            self.assertEqual(config.area_rules, {"payments": "backend"})
            self.assertEqual(config.story_point_field, "custom_points")
            self.assertEqual(config.defect_link_types, ["blocks"])
            self.assertEqual(config.rework_statuses, ["redo"])
            self.assertEqual(config.done_statuses, ["finished"])
            self.assertEqual(config.project_timezone, "US/Pacific")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
