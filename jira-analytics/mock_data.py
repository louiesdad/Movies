"""
Mock Jira data generator — produces realistic project tickets with varying
complexity, types, timelines, and defect counts.
"""

import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class JiraComment:
    author: str
    body: str
    created: datetime


@dataclass
class JiraDefect:
    key: str
    summary: str
    severity: str  # "critical", "major", "minor", "trivial"
    resolved: bool
    resolution_days: Optional[float]


@dataclass
class JiraTicket:
    key: str
    project: str
    type: str  # "Bug", "Story", "Task", "Epic", "Spike"
    priority: str  # "Critical", "High", "Medium", "Low"
    status: str  # "Done", "In Progress", "To Do"
    summary: str
    description: str
    story_points: Optional[int]
    acceptance_criteria: List[str]
    subtasks: List[str]
    dependencies: List[str]
    labels: List[str]
    components: List[str]
    comments: List[JiraComment]
    linked_defects: List[JiraDefect]
    created: datetime
    started: Optional[datetime]
    resolved: Optional[datetime]
    assignee: str
    reporter: str
    sprint: Optional[str]

    @property
    def cycle_time_days(self) -> Optional[float]:
        if self.started and self.resolved:
            return (self.resolved - self.started).total_seconds() / 86400
        return None

    @property
    def lead_time_days(self) -> Optional[float]:
        if self.resolved:
            return (self.resolved - self.created).total_seconds() / 86400
        return None


# ---------------------------------------------------------------------------
# Template pools for generating realistic ticket content
# ---------------------------------------------------------------------------

TEAM_MEMBERS = [
    "Alice Chen", "Bob Martinez", "Carol Smith", "David Kim",
    "Eva Johnson", "Frank Lee", "Grace Park", "Hank Wilson",
]

PROJECTS = {
    "PAY": {
        "name": "Payment Platform",
        "components": ["Gateway", "Checkout", "Invoicing", "Subscriptions", "Fraud Detection"],
    },
    "MOBX": {
        "name": "Mobile Experience",
        "components": ["iOS App", "Android App", "Push Notifications", "Deep Linking", "Offline Mode"],
    },
    "INFRA": {
        "name": "Infrastructure",
        "components": ["CI/CD", "Monitoring", "Database", "Cloud", "Security"],
    },
}

# ---- Story templates (varying complexity) ----

STORY_TEMPLATES = [
    # Simple stories
    {
        "summary": "Add tooltip to dashboard metric cards",
        "description": (
            "Users have requested tooltips on the dashboard metric cards so they can "
            "understand what each number represents without reading docs.\n\n"
            "Show a brief explanation on hover/long-press."
        ),
        "acceptance_criteria": [
            "Tooltip appears on hover (desktop) or long-press (mobile)",
            "Tooltip text matches the metric definition from the glossary",
        ],
        "subtasks": [],
        "labels": ["ux"],
        "points": 2,
    },
    {
        "summary": "Update error message copy for failed payments",
        "description": (
            "The current error messages for failed payments are too technical. "
            "Replace them with user-friendly copy provided by the UX writing team.\n\n"
            "See attached spreadsheet for the new copy strings."
        ),
        "acceptance_criteria": [
            "All 5 error codes display the new copy",
            "Strings are externalized for i18n",
        ],
        "subtasks": ["Update string resources", "QA validation"],
        "labels": ["copy", "ux"],
        "points": 1,
    },
    {
        "summary": "Add loading skeleton to transaction list",
        "description": (
            "Replace the spinner with a skeleton loader for the transaction list view "
            "to improve perceived performance."
        ),
        "acceptance_criteria": [
            "Skeleton matches the layout of actual rows",
            "Animation is smooth at 60fps",
        ],
        "subtasks": [],
        "labels": ["ux", "performance"],
        "points": 2,
    },
    # Medium stories
    {
        "summary": "Implement CSV export for transaction history",
        "description": (
            "Merchants need to export their transaction history as CSV for accounting.\n\n"
            "## Requirements\n"
            "- Date range selector (default: last 30 days, max: 1 year)\n"
            "- Include all visible columns plus internal reference IDs\n"
            "- Handle large datasets (up to 500k rows) via streaming download\n"
            "- Respect user's timezone for date formatting\n\n"
            "## Technical notes\n"
            "Use the existing reporting microservice. Add a new endpoint that streams "
            "CSV rows to avoid memory issues."
        ),
        "acceptance_criteria": [
            "CSV downloads with correct headers",
            "Date range filtering works correctly",
            "Large exports (100k+ rows) complete without timeout",
            "Dates formatted in user's local timezone",
            "Exported data matches on-screen data exactly",
        ],
        "subtasks": [
            "Backend: streaming CSV endpoint",
            "Frontend: download button + date picker",
            "Integration tests for large datasets",
        ],
        "labels": ["reporting", "backend", "frontend"],
        "points": 5,
    },
    {
        "summary": "Build notification preferences screen",
        "description": (
            "Users should be able to control which notifications they receive and through "
            "which channels (email, push, in-app).\n\n"
            "## Requirements\n"
            "- Grouped by category: Transactions, Security, Marketing, System\n"
            "- Per-channel toggles for each category\n"
            "- Changes saved immediately (optimistic UI)\n"
            "- Must sync with existing email preference center\n\n"
            "Wire the UI to the notification-settings API (already exists)."
        ),
        "acceptance_criteria": [
            "All notification categories displayed with correct channel toggles",
            "Toggle state persists across sessions",
            "Optimistic update with rollback on failure",
            "Email preferences synced bi-directionally",
        ],
        "subtasks": [
            "Design review with UX",
            "Implement preferences UI",
            "Wire up API integration",
            "Sync logic with email preference center",
        ],
        "labels": ["notifications", "settings"],
        "points": 5,
    },
    {
        "summary": "Add two-factor authentication via TOTP",
        "description": (
            "Implement TOTP-based 2FA as an option for all user accounts.\n\n"
            "## Requirements\n"
            "- QR code enrollment flow\n"
            "- Backup codes (10 single-use codes)\n"
            "- Remember device option (30 days)\n"
            "- Recovery flow via support ticket if device lost\n"
            "- Enforce 2FA for admin accounts\n\n"
            "## Security considerations\n"
            "- TOTP secrets encrypted at rest (AES-256)\n"
            "- Rate limit verification attempts (5 per minute)\n"
            "- Audit log all 2FA events\n"
            "- Backup codes hashed with bcrypt"
        ),
        "acceptance_criteria": [
            "Users can enroll via QR code with any TOTP app",
            "Backup codes generated and downloadable",
            "Remember-device cookie set with secure flags",
            "Admin accounts forced to enable 2FA",
            "Secrets encrypted at rest",
            "Rate limiting enforced on verification endpoint",
            "All 2FA events appear in audit log",
        ],
        "subtasks": [
            "Backend: TOTP generation and verification",
            "Backend: backup code generation and storage",
            "Backend: device remembrance tokens",
            "Frontend: enrollment wizard",
            "Frontend: login challenge screen",
            "Security review",
            "Documentation update",
        ],
        "labels": ["security", "auth", "backend", "frontend"],
        "points": 13,
    },
    # Complex stories
    {
        "summary": "Migrate payment processing from v2 to v3 gateway API",
        "description": (
            "Our payment gateway provider is deprecating v2 API (EOL: Q3). We need to "
            "migrate all payment flows to v3.\n\n"
            "## Scope\n"
            "- One-time payments\n"
            "- Recurring subscriptions\n"
            "- Refunds and partial refunds\n"
            "- Pre-authorizations and captures\n"
            "- 3D Secure flows\n"
            "- Webhook handling (new event format)\n\n"
            "## Migration strategy\n"
            "1. Implement v3 adapter behind feature flag\n"
            "2. Shadow-run both versions, compare results\n"
            "3. Gradual rollout: 1% → 10% → 50% → 100%\n"
            "4. Monitor error rates and latency at each stage\n\n"
            "## Risks\n"
            "- v3 has different idempotency key format\n"
            "- Webhook signatures use different algorithm\n"
            "- Currency handling changed for zero-decimal currencies\n"
            "- Some error codes remapped\n\n"
            "## Rollback plan\n"
            "Feature flag allows instant rollback to v2. Keep v2 code for 30 days post-migration."
        ),
        "acceptance_criteria": [
            "All 5 payment flows work on v3",
            "Shadow-mode shows <0.1% discrepancy rate",
            "Webhook handler processes new event format",
            "3D Secure challenge flow tested with all card networks",
            "Zero-decimal currencies handled correctly",
            "Feature flag controls rollout percentage",
            "Monitoring dashboards updated for v3 metrics",
            "Runbook updated with new troubleshooting steps",
            "Load test passes at 2x current peak TPS",
        ],
        "subtasks": [
            "Implement v3 payment adapter",
            "Implement v3 subscription adapter",
            "Implement v3 refund adapter",
            "Implement v3 pre-auth/capture adapter",
            "Update 3D Secure flow",
            "New webhook handler",
            "Shadow-mode comparison framework",
            "Feature flag integration",
            "Update monitoring dashboards",
            "Load testing",
            "Update runbook",
            "Coordinate rollout schedule with ops",
        ],
        "labels": ["payments", "migration", "backend", "critical-path"],
        "points": 21,
    },
    {
        "summary": "Implement real-time fraud scoring engine",
        "description": (
            "Build a real-time fraud scoring system that evaluates transactions before "
            "authorization.\n\n"
            "## Requirements\n"
            "- Score each transaction 0-100 (risk level)\n"
            "- Decision in <100ms at p99\n"
            "- Rules engine with configurable thresholds per merchant\n"
            "- ML model integration (pre-trained model from data science team)\n"
            "- Feature extraction: velocity checks, geo anomaly, device fingerprint, "
            "  behavioral biometrics\n"
            "- Manual review queue for scores 60-80\n"
            "- Auto-block for scores >80\n"
            "- Audit trail for all decisions\n\n"
            "## Architecture\n"
            "- Streaming pipeline (Kafka) for real-time features\n"
            "- Redis for velocity counters\n"
            "- gRPC service for scoring\n"
            "- Admin UI for rule management\n\n"
            "## Data requirements\n"
            "- 6 months historical transactions for backtesting\n"
            "- A/B test framework for model comparison\n"
            "- Feedback loop for confirmed fraud cases"
        ),
        "acceptance_criteria": [
            "Scoring latency <100ms at p99",
            "All feature extractors implemented and tested",
            "ML model serves predictions via gRPC",
            "Rules engine supports merchant-level overrides",
            "Manual review queue functional with assignment",
            "Auto-block triggers with notification to merchant",
            "Audit trail captures all decision factors",
            "Backtesting framework validates against 6mo data",
            "A/B test framework allows model comparison",
            "Dashboard shows fraud metrics in real-time",
            "Runbook covers all failure modes",
        ],
        "subtasks": [
            "Design system architecture doc",
            "Set up Kafka topics and schemas",
            "Implement velocity counter service",
            "Implement geo anomaly detector",
            "Implement device fingerprint matcher",
            "Build gRPC scoring service",
            "Integrate ML model",
            "Build rules engine",
            "Build manual review queue UI",
            "Build admin rule management UI",
            "Implement audit trail",
            "Backtesting framework",
            "A/B test framework",
            "Load testing at 2x peak",
            "Security review",
            "Documentation and runbook",
        ],
        "labels": ["fraud", "ml", "backend", "real-time", "critical-path"],
        "points": 34,
    },
]

# ---- Bug templates ----

BUG_TEMPLATES = [
    {
        "summary": "Login button unresponsive on iOS 17.2",
        "description": (
            "## Steps to reproduce\n"
            "1. Open app on iPhone 15 Pro, iOS 17.2\n"
            "2. Enter valid credentials\n"
            "3. Tap Login button\n\n"
            "## Expected\nUser logs in\n\n"
            "## Actual\nButton tap does not register. No network request sent. "
            "Happens ~30% of the time."
        ),
        "acceptance_criteria": ["Login works reliably on iOS 17.x"],
        "subtasks": [],
        "labels": ["ios", "auth"],
        "points": 2,
    },
    {
        "summary": "Currency formatting wrong for Japanese Yen",
        "description": (
            "JPY amounts display with 2 decimal places (e.g., ¥1,000.00) "
            "but JPY is a zero-decimal currency. Should show ¥1,000.\n\n"
            "Affects: transaction list, receipt emails, CSV exports."
        ),
        "acceptance_criteria": [
            "JPY displays without decimals across all surfaces",
            "Other zero-decimal currencies also fixed (KRW, VND)",
        ],
        "subtasks": ["Fix formatter", "Update email templates", "Fix CSV export"],
        "labels": ["i18n", "payments"],
        "points": 3,
    },
    {
        "summary": "Memory leak in dashboard when switching between tabs",
        "description": (
            "## Steps to reproduce\n"
            "1. Open dashboard\n"
            "2. Switch between Overview, Transactions, Analytics tabs rapidly\n"
            "3. Observe memory in DevTools\n\n"
            "## Expected\nMemory stays stable\n\n"
            "## Actual\nMemory grows ~5MB per tab switch. After 50 switches, "
            "page becomes unresponsive.\n\n"
            "## Investigation\n"
            "Likely cause: chart instances not destroyed on tab unmount. Each "
            "Chart.js instance retains canvas context and data arrays."
        ),
        "acceptance_criteria": [
            "Memory stays stable across 100 tab switches",
            "Chart instances properly destroyed on unmount",
            "No detached DOM nodes visible in heap snapshot",
        ],
        "subtasks": [],
        "labels": ["performance", "frontend", "memory"],
        "points": 3,
    },
    {
        "summary": "Webhook retries not respecting exponential backoff",
        "description": (
            "Webhook delivery retries are firing every 5 seconds instead of using "
            "exponential backoff (5s, 30s, 2min, 15min, 1hr).\n\n"
            "This is causing downstream services to be overwhelmed during outages.\n\n"
            "## Root cause\n"
            "The retry delay calculation in WebhookRetryService uses `attempt` instead "
            "of `Math.pow(base, attempt)`. Simple off-by-one in the exponent logic.\n\n"
            "## Impact\n"
            "During the March 15 incident, we sent 50x more webhook traffic than expected "
            "to merchants, causing several to rate-limit us."
        ),
        "acceptance_criteria": [
            "Retries follow exponential backoff schedule",
            "Max 5 retry attempts",
            "Jitter added to prevent thundering herd",
            "Retry schedule logged for debugging",
        ],
        "subtasks": [],
        "labels": ["webhooks", "backend", "reliability"],
        "points": 3,
    },
    {
        "summary": "Race condition in concurrent subscription upgrades",
        "description": (
            "When two subscription upgrade requests arrive within the same second for "
            "the same customer, both succeed, resulting in double-billing.\n\n"
            "## Steps to reproduce\n"
            "1. Use curl to send two upgrade requests simultaneously\n"
            "2. Both return 200 OK\n"
            "3. Customer charged twice\n\n"
            "## Root cause\n"
            "Missing distributed lock on subscription mutations. The read-check-write "
            "pattern is not atomic.\n\n"
            "## Impact\n"
            "~15 customers affected in the last month. All refunded manually.\n\n"
            "## Proposed fix\n"
            "Add Redis-based distributed lock with customer+subscription key. "
            "Alternatively, use database advisory locks."
        ),
        "acceptance_criteria": [
            "Concurrent upgrade requests handled atomically",
            "Second request returns 409 Conflict",
            "No double-billing possible",
            "Lock timeout set to prevent deadlocks",
            "Integration test for concurrent scenario",
        ],
        "subtasks": [
            "Implement distributed locking",
            "Add integration test for concurrent upgrades",
            "Audit other mutation endpoints for same issue",
        ],
        "labels": ["payments", "concurrency", "critical"],
        "points": 5,
    },
]

# ---- Task / Spike templates ----

TASK_TEMPLATES = [
    {
        "type": "Task",
        "summary": "Upgrade Node.js from 18 to 20 LTS",
        "description": "Node 18 EOL approaching. Upgrade all services to Node 20 LTS.",
        "acceptance_criteria": ["All services running on Node 20", "CI green"],
        "subtasks": [],
        "labels": ["infra", "maintenance"],
        "points": 3,
    },
    {
        "type": "Task",
        "summary": "Set up Datadog APM for checkout service",
        "description": (
            "Instrument the checkout service with Datadog APM tracing. "
            "Include custom spans for payment gateway calls and database queries."
        ),
        "acceptance_criteria": [
            "Traces visible in Datadog",
            "Custom spans for external calls",
            "Service map shows checkout dependencies",
        ],
        "subtasks": [],
        "labels": ["monitoring", "observability"],
        "points": 3,
    },
    {
        "type": "Spike",
        "summary": "Evaluate GraphQL federation for API gateway",
        "description": (
            "Research whether Apollo Federation or similar would help us unify "
            "our 12 REST microservice APIs into a single graph.\n\n"
            "## Questions to answer\n"
            "- Performance overhead at our scale (10k RPM)\n"
            "- Migration path from REST\n"
            "- Team training requirements\n"
            "- Tooling maturity (monitoring, testing)\n\n"
            "Timebox: 1 week. Produce a recommendation doc."
        ),
        "acceptance_criteria": [
            "Recommendation document published",
            "Performance benchmarks included",
            "Migration effort estimated",
        ],
        "subtasks": [
            "Prototype with 2 services",
            "Benchmark performance",
            "Write recommendation doc",
        ],
        "labels": ["architecture", "research"],
        "points": 5,
    },
    {
        "type": "Spike",
        "summary": "Investigate PCI DSS v4.0 compliance gaps",
        "description": (
            "PCI DSS v4.0 takes effect next quarter. Audit our current controls "
            "against the new requirements and identify gaps.\n\n"
            "Focus areas:\n"
            "- Enhanced authentication requirements\n"
            "- New encryption standards\n"
            "- Expanded logging requirements\n"
            "- Third-party risk management"
        ),
        "acceptance_criteria": [
            "Gap analysis document complete",
            "Remediation backlog created",
            "Timeline proposed for compliance",
        ],
        "subtasks": [
            "Review v4.0 changes",
            "Audit current controls",
            "Interview security team",
            "Draft gap analysis",
        ],
        "labels": ["security", "compliance"],
        "points": 8,
    },
]


def _random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def _generate_comments(ticket_type: str, complexity: int) -> List[JiraComment]:
    comment_pool = [
        "Can you clarify the expected behavior for edge case X?",
        "I've updated the design doc with the latest architecture diagram.",
        "QA found an issue during regression — see linked defect.",
        "Deployment to staging looks good. Ready for production.",
        "Need input from the security team before we proceed.",
        "PR is up for review: https://github.com/example/repo/pull/123",
        "This is blocked by the database migration in INFRA-42.",
        "Reduced scope for this sprint — moving subtask 3 to next sprint.",
        "Performance benchmarks look good: p99 latency < 50ms.",
        "Customer escalation — bumping priority to High.",
        "Added integration tests covering the main flow.",
        "Had to rework the approach after code review feedback.",
        "Merging today. Will monitor error rates post-deploy.",
        "Rolled back due to unexpected 5xx spike. Investigating.",
        "Root cause identified. Fix incoming.",
    ]
    count = min(complexity // 2, len(comment_pool))
    count = max(1, count + random.randint(-1, 2))
    selected = random.sample(comment_pool, min(count, len(comment_pool)))
    base = datetime(2025, 1, 1)
    return [
        JiraComment(
            author=random.choice(TEAM_MEMBERS),
            body=text,
            created=base + timedelta(days=random.randint(0, 90)),
        )
        for text in selected
    ]


def _generate_defects(ticket: dict, ticket_key: str) -> List[JiraDefect]:
    """Generate linked defects based on ticket complexity."""
    points = ticket.get("points", 1)
    # More complex tickets tend to have more defects
    if points <= 2:
        max_defects = 1
        defect_chance = 0.3
    elif points <= 5:
        max_defects = 2
        defect_chance = 0.5
    elif points <= 13:
        max_defects = 3
        defect_chance = 0.7
    else:
        max_defects = 5
        defect_chance = 0.85

    defects = []
    if random.random() < defect_chance:
        num = random.randint(1, max_defects)
        severities = ["critical", "major", "minor", "trivial"]
        sev_weights = [0.1, 0.3, 0.4, 0.2]
        for i in range(num):
            sev = random.choices(severities, weights=sev_weights, k=1)[0]
            resolved = random.random() < 0.85
            defects.append(JiraDefect(
                key=f"{ticket_key}-D{i+1}",
                summary=f"Defect found during testing of {ticket_key}",
                severity=sev,
                resolved=resolved,
                resolution_days=random.uniform(0.5, 5.0) if resolved else None,
            ))
    return defects


def generate_project_tickets(project_key: str, count: int = 30,
                              seed: int = 42) -> List[JiraTicket]:
    """Generate a set of realistic mock Jira tickets for a project."""
    random.seed(seed + hash(project_key))
    project = PROJECTS[project_key]
    tickets: List[JiraTicket] = []

    all_templates = []
    for t in STORY_TEMPLATES:
        all_templates.append({**t, "type": "Story"})
    for t in BUG_TEMPLATES:
        all_templates.append({**t, "type": "Bug"})
    for t in TASK_TEMPLATES:
        all_templates.append(t)

    base_date = datetime(2025, 1, 6)

    for i in range(count):
        template = random.choice(all_templates)
        key = f"{project_key}-{i+1}"
        points = template.get("points", random.choice([1, 2, 3, 5]))

        created = base_date + timedelta(days=random.randint(0, 120))

        # Time to start: more complex tickets often wait longer in backlog
        days_to_start = random.uniform(1, 5) + (points * random.uniform(0.2, 0.8))
        started = created + timedelta(days=days_to_start)

        # Cycle time correlated with complexity but with realistic variance
        base_cycle = points * random.uniform(0.8, 2.5)
        # Add noise: sometimes simple things take long, complex things go fast
        noise = random.gauss(0, points * 0.3)
        cycle_days = max(0.5, base_cycle + noise)

        resolved = started + timedelta(days=cycle_days)

        # 10% chance ticket is still in progress
        is_done = random.random() < 0.90
        status = "Done" if is_done else random.choice(["In Progress", "To Do"])

        priority_weights = {"Critical": 0.05, "High": 0.25, "Medium": 0.50, "Low": 0.20}
        priority = random.choices(
            list(priority_weights.keys()),
            weights=list(priority_weights.values()),
            k=1,
        )[0]

        defects = _generate_defects(template, key) if is_done else []
        comments = _generate_comments(template["type"], points)

        ticket = JiraTicket(
            key=key,
            project=project_key,
            type=template["type"],
            priority=priority,
            status=status,
            summary=template["summary"],
            description=template["description"],
            story_points=points,
            acceptance_criteria=template.get("acceptance_criteria", []),
            subtasks=template.get("subtasks", []),
            dependencies=[f"{project_key}-{random.randint(1, max(1, i))}"
                          for _ in range(random.randint(0, 2))] if i > 0 else [],
            labels=template.get("labels", []),
            components=random.sample(project["components"],
                                      k=random.randint(1, min(3, len(project["components"])))),
            comments=comments,
            linked_defects=defects,
            created=created,
            started=started if is_done or status == "In Progress" else None,
            resolved=resolved if is_done else None,
            assignee=random.choice(TEAM_MEMBERS),
            reporter=random.choice(TEAM_MEMBERS),
            sprint=f"Sprint {(i // 8) + 1}" if is_done else None,
        )
        tickets.append(ticket)

    return tickets
