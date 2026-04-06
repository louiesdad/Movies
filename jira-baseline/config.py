"""
Configuration management — loads YAML project config with defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class ProjectConfig:
    """Project-specific configuration with sensible defaults."""
    # Status overrides: raw_status -> phase name
    status_overrides: Dict[str, str] = field(default_factory=dict)
    # Area overrides: component/label -> area name
    area_rules: Dict[str, str] = field(default_factory=dict)
    # Custom Jira field name for story points
    story_point_field: str = "story_points"
    # Link type names that indicate a defect relationship
    defect_link_types: List[str] = field(
        default_factory=lambda: ["is caused by", "causes", "defect", "bug"]
    )
    # Statuses that indicate rework
    rework_statuses: List[str] = field(
        default_factory=lambda: ["reopened", "rework", "reopen"]
    )
    # Statuses that indicate done
    done_statuses: List[str] = field(
        default_factory=lambda: ["done", "closed", "resolved", "completed",
                                  "deployed", "released", "shipped", "verified"]
    )
    # Project timezone for display (analysis uses UTC)
    project_timezone: str = "UTC"


def load_config(path: Optional[str] = None) -> ProjectConfig:
    """Load project config from YAML file, or return defaults."""
    if path is None:
        return ProjectConfig()

    if not HAS_YAML:
        raise ImportError(
            "PyYAML is required for config files. Install with: pip install pyyaml"
        )

    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    defaults = ProjectConfig()
    return ProjectConfig(
        status_overrides=raw.get("status_overrides", {}),
        area_rules=raw.get("area_rules", {}),
        story_point_field=raw.get("story_point_field", "story_points"),
        defect_link_types=raw.get("defect_link_types",
                                   defaults.defect_link_types),
        rework_statuses=raw.get("rework_statuses",
                                 defaults.rework_statuses),
        done_statuses=raw.get("done_statuses", defaults.done_statuses),
        project_timezone=raw.get("project_timezone", "UTC"),
    )
