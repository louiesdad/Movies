"""
Config validation — checks a YAML config file for correctness and reports
warnings for suspicious values.
"""

from typing import Dict, List, Tuple

from models import Phase, Area


VALID_PHASES = {p.value for p in Phase if p != Phase.UNKNOWN}
VALID_AREAS = {a.value for a in Area}


def validate_config(raw: dict) -> Tuple[List[str], List[str]]:
    """Validate a raw config dict (from YAML).

    Returns (errors, warnings).
    Errors are problems that will cause incorrect behavior.
    Warnings are suspicious values that might be unintentional.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # --- status_overrides ---
    if "status_overrides" in raw:
        val = raw["status_overrides"]
        if not isinstance(val, dict):
            errors.append("status_overrides must be a mapping (key: value)")
        else:
            for status, phase in val.items():
                if not isinstance(phase, str):
                    errors.append(f"status_overrides['{status}']: value must be a string, got {type(phase).__name__}")
                elif phase.lower() not in VALID_PHASES:
                    errors.append(
                        f"status_overrides['{status}']: invalid phase '{phase}'. "
                        f"Valid: {', '.join(sorted(VALID_PHASES))}"
                    )

    # --- area_rules ---
    if "area_rules" in raw:
        val = raw["area_rules"]
        if not isinstance(val, dict):
            errors.append("area_rules must be a mapping (key: value)")
        else:
            for key, area in val.items():
                if not isinstance(area, str):
                    errors.append(f"area_rules['{key}']: value must be a string, got {type(area).__name__}")
                elif area.lower() not in VALID_AREAS:
                    errors.append(
                        f"area_rules['{key}']: invalid area '{area}'. "
                        f"Valid: {', '.join(sorted(VALID_AREAS))}"
                    )

    # --- list fields ---
    for field_name in ["defect_link_types", "rework_statuses", "done_statuses"]:
        if field_name in raw:
            val = raw[field_name]
            if not isinstance(val, list):
                errors.append(f"{field_name} must be a list")
            else:
                for i, item in enumerate(val):
                    if not isinstance(item, str):
                        errors.append(f"{field_name}[{i}]: must be a string, got {type(item).__name__}")
                if len(val) == 0:
                    warnings.append(f"{field_name} is empty — defaults will not apply")

    # --- story_point_field ---
    if "story_point_field" in raw:
        val = raw["story_point_field"]
        if not isinstance(val, str):
            errors.append(f"story_point_field must be a string, got {type(val).__name__}")
        elif " " in val:
            warnings.append(f"story_point_field contains spaces: '{val}' — this is unusual for a Jira field name")

    # --- project_timezone ---
    if "project_timezone" in raw:
        val = raw["project_timezone"]
        if not isinstance(val, str):
            errors.append(f"project_timezone must be a string, got {type(val).__name__}")

    # --- unknown keys ---
    known_keys = {
        "status_overrides", "area_rules", "story_point_field",
        "defect_link_types", "rework_statuses", "done_statuses",
        "project_timezone",
    }
    unknown = set(raw.keys()) - known_keys
    for key in sorted(unknown):
        warnings.append(f"Unknown config key: '{key}' — will be ignored")

    return errors, warnings
