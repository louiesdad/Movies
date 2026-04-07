"""Tests for classifier.py — size and area classification."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from classifier import classify_size, classify_area
from models import Size, Area, Confidence
from config import ProjectConfig


class TestSizeClassification(unittest.TestCase):

    def test_story_points_small(self):
        for pts in [1, 2, 3]:
            size, conf = classify_size(story_points=pts)
            self.assertEqual(size, Size.SMALL, f"Failed for {pts}")
            self.assertEqual(conf, Confidence.HIGH)

    def test_story_points_medium(self):
        for pts in [4, 5, 6, 7, 8]:
            size, conf = classify_size(story_points=pts)
            self.assertEqual(size, Size.MEDIUM, f"Failed for {pts}")
            self.assertEqual(conf, Confidence.HIGH)

    def test_story_points_large(self):
        for pts in [9, 10, 13, 21, 34]:
            size, conf = classify_size(story_points=pts)
            self.assertEqual(size, Size.LARGE, f"Failed for {pts}")
            self.assertEqual(conf, Confidence.HIGH)

    def test_zero_points_uses_fallback(self):
        size, conf = classify_size(story_points=0, description="short")
        self.assertNotEqual(conf, Confidence.HIGH)

    def test_none_points_uses_fallback(self):
        size, conf = classify_size(story_points=None, description="short desc")
        self.assertNotEqual(conf, Confidence.HIGH)

    def test_fallback_small(self):
        size, conf = classify_size(
            story_points=None,
            description="Fix button color",
            acceptance_criteria=["button is blue"],
            subtasks=[],
            dependencies=[],
        )
        self.assertEqual(size, Size.SMALL)

    def test_fallback_large(self):
        long_desc = "word " * 200  # 200 words
        size, conf = classify_size(
            story_points=None,
            description=long_desc,
            acceptance_criteria=["ac1", "ac2", "ac3", "ac4", "ac5", "ac6"],
            subtasks=["s1", "s2", "s3", "s4", "s5"],
            dependencies=["d1", "d2", "d3"],
        )
        self.assertEqual(size, Size.LARGE)


class TestAreaClassification(unittest.TestCase):

    def test_frontend_component(self):
        area, conf = classify_area(components=["Web UI"], labels=[])
        self.assertEqual(area, Area.FRONTEND)

    def test_backend_component(self):
        area, conf = classify_area(components=["API"], labels=[])
        self.assertEqual(area, Area.BACKEND)

    def test_infra_labels(self):
        area, conf = classify_area(components=[], labels=["devops", "terraform"])
        self.assertEqual(area, Area.INFRA)

    def test_mobile_component(self):
        area, conf = classify_area(components=["iOS App"], labels=[])
        self.assertEqual(area, Area.MOBILE)

    def test_data_labels(self):
        area, conf = classify_area(components=[], labels=["etl", "data"])
        self.assertEqual(area, Area.DATA)

    def test_mixed_signals(self):
        area, conf = classify_area(
            components=["API", "Web UI"],
            labels=["frontend", "backend"],
        )
        self.assertEqual(area, Area.MIXED)

    def test_unknown_area(self):
        area, conf = classify_area(components=[], labels=[])
        self.assertEqual(area, Area.UNKNOWN)
        self.assertEqual(conf, Confidence.LOW)

    def test_yaml_override(self):
        config = ProjectConfig(area_rules={"payments": "backend"})
        area, conf = classify_area(
            components=["Payments"], labels=[], config=config)
        self.assertEqual(area, Area.BACKEND)

    def test_summary_keyword_fallback(self):
        area, conf = classify_area(
            components=[], labels=[],
            summary="Fix iOS crash on login screen")
        self.assertEqual(area, Area.MOBILE)


if __name__ == "__main__":
    unittest.main()
