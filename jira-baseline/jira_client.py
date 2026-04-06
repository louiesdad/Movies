"""
Jira client — fetches issues and changelog from Jira REST API.

Supports two modes:
  - Live: connects to a real Jira instance via REST API
  - Sample: generates realistic sample data for development/testing

The sample mode produces changelog-driven data with varied statuses,
types, and realistic timing distributions.
"""

import hashlib
import random
from datetime import datetime, timedelta
from typing import List, Optional

from models import JiraIssue, StatusTransition, Phase
from normalizer import StatusNormalizer


class JiraClient:
    """Interface for fetching Jira issues."""

    def fetch_issues(
        self,
        project_key: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> List[JiraIssue]:
        raise NotImplementedError("Subclasses must implement fetch_issues")


class LiveJiraClient(JiraClient):
    """Connects to a real Jira instance.

    Placeholder for Phase 1 — the real implementation will use
    the Jira REST API with pagination and changelog expansion.
    """

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token

    def fetch_issues(self, project_key, since=None, until=None):
        raise NotImplementedError(
            "Live Jira client not yet implemented. Use SampleJiraClient for development."
        )


class SampleJiraClient(JiraClient):
    """Generates realistic sample data for development and testing.

    Produces changelog-driven issues with varied statuses, types,
    and realistic timing. Deterministic for a given project key + seed.
    """

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._normalizer = StatusNormalizer()

    def fetch_issues(
        self,
        project_key: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        count: int = 50,
    ) -> List[JiraIssue]:
        # Deterministic seeding
        key_hash = int(hashlib.md5(project_key.encode()).hexdigest(), 16) % (2**31)
        random.seed(self._seed + key_hash)

        issues: List[JiraIssue] = []
        base_date = datetime(2025, 1, 6)

        templates = self._build_templates()

        for i in range(count):
            template = random.choice(templates)
            key = f"{project_key}-{i + 1}"
            points = template.get("points", random.choice([1, 2, 3, 5, 8]))
            is_done = random.random() < 0.88
            is_epic = template["type"] == "Epic"
            effective_points = points or 3  # use 3 for timing calculations when points=None

            created = base_date + timedelta(days=random.randint(0, 300))

            # Filter by analysis window
            if since and created < since:
                continue
            if until and created > until:
                continue

            # Generate changelog
            changelog = []
            started = None
            resolved = None
            final_status = "Backlog"

            if is_done or random.random() < 0.7:
                # Transition to active
                days_to_start = random.uniform(0.5, 8) + (effective_points * random.uniform(0.1, 0.5))
                started = created + timedelta(days=days_to_start)
                active_status = random.choice([
                    "In Progress", "In Development", "Coding",
                ])
                changelog.append(StatusTransition(
                    timestamp=started,
                    from_status="Backlog",
                    to_status=active_status,
                    from_phase=Phase.BACKLOG,
                    to_phase=Phase.ACTIVE,
                ))
                final_status = active_status

            if is_done:
                # Optionally go through review
                if random.random() < 0.6:
                    review_start = started + timedelta(
                        days=effective_points * random.uniform(0.5, 1.5))
                    review_status = random.choice([
                        "In Review", "Code Review", "In QA", "Testing",
                    ])
                    changelog.append(StatusTransition(
                        timestamp=review_start,
                        from_status=final_status,
                        to_status=review_status,
                        from_phase=Phase.ACTIVE,
                        to_phase=Phase.REVIEW,
                    ))
                    final_status = review_status

                # Rework: 15% chance of backward movement
                has_rework = random.random() < 0.15
                if has_rework and len(changelog) >= 1:
                    rework_time = changelog[-1].timestamp + timedelta(
                        days=random.uniform(0.5, 2))
                    changelog.append(StatusTransition(
                        timestamp=rework_time,
                        from_status=final_status,
                        to_status="In Progress",
                        from_phase=changelog[-1].to_phase,
                        to_phase=Phase.ACTIVE,
                    ))
                    # Back to review
                    re_review = rework_time + timedelta(
                        days=random.uniform(0.5, 2))
                    changelog.append(StatusTransition(
                        timestamp=re_review,
                        from_status="In Progress",
                        to_status="In Review",
                        from_phase=Phase.ACTIVE,
                        to_phase=Phase.REVIEW,
                    ))
                    final_status = "In Review"

                # Resolve
                cycle_days = max(0.5, effective_points * random.uniform(0.8, 2.5)
                                 + random.gauss(0, effective_points * 0.3))
                resolved = started + timedelta(days=cycle_days)
                done_status = random.choice([
                    "Done", "Closed", "Resolved", "Deployed", "Verified",
                ])
                changelog.append(StatusTransition(
                    timestamp=resolved,
                    from_status=final_status,
                    to_status=done_status,
                    from_phase=Phase.REVIEW if "review" in final_status.lower()
                                            or "qa" in final_status.lower()
                                            else Phase.ACTIVE,
                    to_phase=Phase.DONE,
                ))
                final_status = done_status

            # Generate linked bugs (for done tickets)
            linked_bugs = []
            if is_done and random.random() < 0.3:
                bug_count = random.randint(1, 2)
                linked_bugs = [f"{project_key}-BUG-{i+1}-{j+1}"
                               for j in range(bug_count)]

            # Resolution for duplicates
            resolution = None
            is_duplicate = is_done and random.random() < 0.05
            if is_duplicate:
                resolution = "Duplicate"
            elif is_done:
                resolution = "Done"

            components = random.sample(
                self._components(), k=random.randint(1, 2))
            labels = random.sample(
                self._labels(), k=random.randint(0, 3))

            issues.append(JiraIssue(
                key=key,
                project=project_key,
                issue_type=template["type"],
                status=final_status,
                resolution=resolution,
                priority=random.choices(
                    ["Critical", "High", "Medium", "Low"],
                    weights=[0.05, 0.25, 0.50, 0.20], k=1)[0],
                summary=template["summary"],
                description=template["description"],
                story_points=points if not is_epic else None,
                components=components,
                labels=labels,
                acceptance_criteria=template.get("acs", []),
                subtasks=template.get("subtasks", []),
                dependencies=[f"{project_key}-{random.randint(1, max(1, i))}"
                              for _ in range(random.randint(0, 2))] if i > 0 else [],
                linked_bugs=linked_bugs,
                created=created,
                resolved=resolved,
                assignee=random.choice([
                    "Alice", "Bob", "Carol", "David", "Eva", "Frank"]),
                sprint=f"Sprint {(i // 8) + 1}" if is_done else None,
                changelog=changelog,
            ))

        return issues

    def _build_templates(self):
        return [
            {"type": "Story", "points": 2, "summary": "Add tooltip to dashboard cards",
             "description": "Show tooltips on hover for metric cards.",
             "acs": ["Tooltip appears on hover", "Text matches glossary"]},
            {"type": "Story", "points": 5, "summary": "Implement CSV export",
             "description": "Merchants need CSV export for transactions.\n\n## Requirements\n- Date range selector\n- Stream large datasets\n- Timezone formatting",
             "acs": ["CSV downloads correctly", "Date filtering works", "Large exports complete"],
             "subtasks": ["Backend endpoint", "Frontend button", "Integration tests"]},
            {"type": "Story", "points": 8, "summary": "Build notification preferences",
             "description": "Users control notification channels.\n\n## Requirements\n- Category grouping\n- Per-channel toggles\n- Optimistic UI\n- Sync with email prefs",
             "acs": ["Categories displayed", "Toggles persist", "Optimistic update works", "Email sync"],
             "subtasks": ["Design review", "Preferences UI", "API wiring", "Email sync"]},
            {"type": "Story", "points": 13, "summary": "Add two-factor authentication",
             "description": "TOTP-based 2FA.\n\n## Requirements\n- QR enrollment\n- Backup codes\n- Remember device\n- Enforce for admins\n\n## Security\n- Encrypted secrets\n- Rate limiting\n- Audit logging",
             "acs": ["QR enrollment works", "Backup codes generated", "Admin enforcement", "Audit log"],
             "subtasks": ["TOTP backend", "Backup codes", "Device tokens", "Enrollment UI", "Challenge screen"]},
            {"type": "Story", "points": 21, "summary": "Migrate payment gateway v2 to v3",
             "description": "Payment gateway v2 EOL.\n\n## Scope\n- One-time payments\n- Subscriptions\n- Refunds\n- 3D Secure\n\n## Migration strategy\n1. Feature flag\n2. Shadow mode\n3. Gradual rollout\n\n## Risks\n- Idempotency format change\n- Webhook signature change",
             "acs": ["All flows work on v3", "Shadow mode <0.1% discrepancy", "Feature flag controls rollout"],
             "subtasks": ["v3 payment adapter", "v3 subscription adapter", "v3 refund adapter", "Webhook handler", "Shadow mode", "Load test"]},
            {"type": "Bug", "points": 2, "summary": "Login button unresponsive on iOS 17",
             "description": "## Steps to reproduce\n1. Open app on iOS 17\n2. Enter credentials\n3. Tap Login\n\n## Actual\nButton tap doesn't register 30% of the time.",
             "acs": ["Login works reliably on iOS 17"]},
            {"type": "Bug", "points": 3, "summary": "Currency formatting wrong for JPY",
             "description": "JPY shows 2 decimal places but it's a zero-decimal currency.",
             "acs": ["JPY displays without decimals", "Other zero-decimal currencies fixed"],
             "subtasks": ["Fix formatter", "Update emails", "Fix CSV export"]},
            {"type": "Bug", "points": 5, "summary": "Race condition in subscription upgrades",
             "description": "Concurrent upgrade requests cause double-billing.\n\n## Root cause\nMissing distributed lock on subscription mutations.",
             "acs": ["Concurrent requests handled atomically", "No double-billing", "Integration test"],
             "subtasks": ["Distributed locking", "Concurrent test", "Audit other endpoints"]},
            {"type": "Task", "points": 3, "summary": "Upgrade Node.js to v20 LTS",
             "description": "Node 18 EOL approaching.",
             "acs": ["All services on Node 20", "CI green"]},
            {"type": "Task", "points": 3, "summary": "Set up Datadog APM",
             "description": "Instrument checkout service with Datadog APM tracing.",
             "acs": ["Traces visible", "Custom spans for external calls"]},
            {"type": "Spike", "points": 5, "summary": "Evaluate GraphQL federation",
             "description": "Research Apollo Federation for API gateway.\n\n## Questions\n- Performance overhead\n- Migration path\n- Training needs",
             "acs": ["Recommendation doc", "Benchmarks included"]},
            {"type": "Epic", "points": None, "summary": "Q2 Platform Reliability Initiative",
             "description": "Epic tracking all reliability improvements for Q2.",
             "acs": []},
        ]

    def _components(self):
        return ["Gateway", "Checkout", "API", "iOS App", "Web UI",
                "CI/CD", "Database", "Auth", "Analytics"]

    def _labels(self):
        return ["frontend", "backend", "infra", "mobile", "security",
                "performance", "ux", "api", "data", "devops"]
