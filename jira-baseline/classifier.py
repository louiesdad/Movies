"""
Classifier — assigns size and area buckets to tickets.
"""

from typing import Dict, List, Optional, Tuple

from models import Size, Area, Confidence
from config import ProjectConfig


# ---------------------------------------------------------------------------
# Size classification
# ---------------------------------------------------------------------------

def classify_size(
    story_points: Optional[float],
    description: str = "",
    acceptance_criteria: Optional[List[str]] = None,
    subtasks: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
) -> Tuple[Size, Confidence]:
    """Classify ticket size from story points or fallback heuristics.

    Returns (size, confidence).
    """
    ac = acceptance_criteria or []
    st = subtasks or []
    deps = dependencies or []

    # Primary: story points
    if story_points is not None and story_points > 0:
        if story_points <= 3:
            return Size.SMALL, Confidence.HIGH
        elif story_points <= 8:
            return Size.MEDIUM, Confidence.HIGH
        else:
            return Size.LARGE, Confidence.HIGH

    # Fallback: content heuristic
    word_count = len(description.split()) if description else 0
    ac_count = len(ac)
    subtask_count = len(st)
    dep_count = len(deps)

    # Count how many signals point to each size
    small_signals = 0
    large_signals = 0

    if word_count < 50:
        small_signals += 1
    elif word_count > 150:
        large_signals += 1

    if ac_count <= 2:
        small_signals += 1
    elif ac_count > 5:
        large_signals += 1

    if subtask_count <= 1:
        small_signals += 1
    elif subtask_count > 4:
        large_signals += 1

    if dep_count <= 1:
        small_signals += 1
    elif dep_count > 2:
        large_signals += 1

    if large_signals >= 2:
        return Size.LARGE, Confidence.MEDIUM
    elif small_signals >= 3:
        return Size.SMALL, Confidence.MEDIUM
    elif large_signals >= 1 and small_signals >= 1:
        # Conflicting signals
        return Size.UNKNOWN, Confidence.LOW
    elif small_signals >= 2:
        return Size.SMALL, Confidence.LOW
    else:
        return Size.MEDIUM, Confidence.MEDIUM


# ---------------------------------------------------------------------------
# Area classification
# ---------------------------------------------------------------------------

_DEFAULT_AREA_KEYWORDS: Dict[Area, List[str]] = {
    Area.FRONTEND: [
        "ui", "web", "react", "vue", "angular", "css", "browser", "client",
        "frontend", "front-end", "sass", "less", "html", "javascript", "typescript",
        "next", "nuxt", "svelte", "tailwind", "webpack", "vite",
    ],
    Area.BACKEND: [
        "api", "service", "server", "gateway", "auth", "payments", "checkout",
        "backend", "back-end", "rest", "graphql", "grpc", "microservice",
        "endpoint", "middleware", "webhook", "queue",
    ],
    Area.INFRA: [
        "infra", "terraform", "cloud", "deploy", "ci", "cd", "k8s",
        "database", "kubernetes", "docker", "aws", "gcp", "azure",
        "monitoring", "logging", "devops", "pipeline", "helm", "nginx",
        "redis", "kafka", "postgres", "mysql", "migration",
    ],
    Area.MOBILE: [
        "ios", "android", "react-native", "mobile", "swift", "kotlin",
        "flutter", "expo", "xcode", "gradle", "app store", "play store",
    ],
    Area.DATA: [
        "etl", "warehouse", "analytics", "pipeline", "airflow", "dbt",
        "data", "bigquery", "snowflake", "spark", "ml", "model",
        "dataset", "reporting", "tableau", "looker",
    ],
}


def classify_area(
    components: List[str],
    labels: List[str],
    summary: str = "",
    config: Optional[ProjectConfig] = None,
) -> Tuple[Area, Confidence]:
    """Classify ticket area from components, labels, and summary.

    Resolution order:
    1. YAML override (exact component/label match)
    2. Component keyword match
    3. Label keyword match
    4. Summary keyword match
    5. Fallback: mixed or unknown
    """
    area_overrides = (config.area_rules if config else {})

    # Collect all area hits with their source strength
    hits: Dict[Area, int] = {}

    def _record_hit(area: Area, weight: int = 1):
        hits[area] = hits.get(area, 0) + weight

    # 1. Check YAML overrides (highest priority)
    for item in components + labels:
        item_lower = item.lower().strip()
        if item_lower in area_overrides:
            try:
                area = Area(area_overrides[item_lower])
                _record_hit(area, weight=10)
            except ValueError:
                pass

    # 2-3. Component and label keyword matching
    for item in components:
        _match_keywords(item.lower(), hits, weight=3)
    for item in labels:
        _match_keywords(item.lower(), hits, weight=2)

    # 4. Summary keyword matching (weakest signal)
    if summary:
        _match_keywords(summary.lower(), hits, weight=1)

    if not hits:
        return Area.UNKNOWN, Confidence.LOW

    sorted_areas = sorted(hits.items(), key=lambda x: x[1], reverse=True)
    top_area, top_score = sorted_areas[0]

    # Multiple strong matches → mixed
    if len(sorted_areas) > 1:
        second_area, second_score = sorted_areas[1]
        if second_score >= top_score * 0.7:
            return Area.MIXED, Confidence.MEDIUM

    # Confidence based on score strength
    if top_score >= 5:
        return top_area, Confidence.HIGH
    elif top_score >= 2:
        return top_area, Confidence.MEDIUM
    else:
        return top_area, Confidence.LOW


def _match_keywords(text: str, hits: Dict[Area, int], weight: int = 1):
    """Match text against default area keyword lists."""
    for area, keywords in _DEFAULT_AREA_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                hits[area] = hits.get(area, 0) + weight
                break  # one match per area per text is enough
