# About Earthly Lunar

Earthly Lunar is a **guardrails engine** for your engineering stack. It automatically enforces your organization's engineering standards across all code repositories and CI/CD pipelines.

## The Problem Lunar Solves

Engineering teams struggle to enforce standards at scale. Typically, standards are communicated through:

- Slack announcements
- Email blasts
- Wiki pages
- Postmortem action items
- Jira tickets
- All-hands meetings

These messages get lost in the noise. Tickets get buried in backlogs. Quarters pass, and the same types of incidents happen again. Manual coordination across hundreds of engineers is expensive and ineffective.

**The math doesn't work**: 100 standards × 500 engineers = 50,000 touchpoints of out-of-context communication.

## How Lunar Works

Lunar takes a fundamentally different approach: instead of broadcasting standards to every engineer, it delivers **contextual feedback exactly where and when it matters**—in pull requests.

### Integration Points

Lunar connects to your engineering ecosystem through two integration points:

1. **GitHub App**: A one-click installation that monitors your code repositories, reacts to code changes, and provides PR feedback.

2. **CI/CD Agent**: A lightweight agent that runs alongside your CI/CD runners and detects pipeline processes via syscalls. Compatible with all major CI vendors.

Both integrations are centralized—no repo-by-repo setup required.

### The Execution Flow

Once integrated, Lunar automatically runs these steps on every code change:

**Step 1: Automatic Data Collection**

Lunar collects application metadata from:
- Source code and configuration files
- Dockerfiles, Kubernetes manifests, and Helm charts
- Infrastructure-as-code files
- Test results and security scans
- Build artifacts and SBOMs
- Deployment configurations
- And much more

**Step 2: Centralized SDLC Data**

All collected data is normalized into a structured JSON document that reflects the overall posture of each application. This data is stored centrally and updated continuously.

**Step 3: Guardrail Evaluation and Feedback**

Guardrails define the practices your organization wants to enforce. Lunar evaluates each application's data against your defined standards and provides real-time feedback directly in developer pull requests.

## Key Concepts

### The Component JSON (Technical)

At the heart of Lunar is the **Component JSON**—a JSON document that accumulates all metadata about a component (service/library). This is the data contract between collectors and policies:

1. **Collectors** write data to the Component JSON (e.g., `{"repo": {"readme_exists": true}}`)
2. **Policies** read from the Component JSON to evaluate compliance

The structure is arbitrary—collectors define what they write, and policies know what to read. This decoupling allows collectors and policies to be developed independently.

### Guardrails

Guardrails are your engineering standards expressed as code. They verify that applications comply with organizational requirements—things like:

- Code coverage tools must be used
- Kubernetes manifests must define resource limits
- Docker images must not use `:latest` tags
- Security scanners must be run in CI
- CODEOWNERS files must be valid
- SBOMs must be generated for compliance

Lunar includes 100+ pre-built guardrails across categories like testing, security, compliance, operational readiness, and infrastructure. You can also create custom guardrails for your unique standards.

### Gradual Enforcement

Not every standard needs to block deployments immediately. Lunar supports five enforcement levels:

1. `draft`: Visible only to the platform team for testing
2. `score`: Affects application health scores in dashboards
3. `report-pr`: Adds comments to pull requests without blocking
4. `block-pr`: Prevents pull requests from merging
5. `block-release`: Stops production deployments
6. `block-pr-and-release`: Blocks both PRs and releases

This allows teams to roll out guardrails progressively—starting with visibility and guidance, then tightening enforcement as adoption grows.

### Contextual Feedback

Instead of broadcasting every standard to every engineer, Lunar shows developers only the standards relevant to their specific pull request. This eliminates context-switching and ensures engineers see requirements exactly when they need to act on them.

### Executive Visibility

Lunar provides dashboards showing standards adherence across every service in the organization. Leadership can see:

- Overall adherence percentages
- Domain and team health scores
- Trends over time
- Which standards need attention

This makes the organization continuously audit-ready.

## The Result

With Lunar:

- New standards are enforced in **minutes, not quarters**
- **100% of accidental rubber-stamping** is eliminated
- Organizations can enforce **30x more standards** than before
- Developer friction is reduced by **80%** through contextual feedback

Standards become self-enforcing. No manual checklists. No forever-backlogged tickets. No release-day surprises.

## Why Not Just Use CI?

CI is essential for repository-specific verification like building and testing. But for global standards enforcement, it falls short:

| Challenge | CI Only | Lunar |
|-----------|---------|-------|
| Integration | Manual, repo-by-repo | Central, one-time setup |
| Enforcement | All-or-nothing blocking | Gradual levels |
| Rollout time | Quarters | Minutes |
| Visibility | Scattered across pipelines | Unified dashboard |

**Use CI for builds and tests. Use Lunar for organization-wide guardrails.**
