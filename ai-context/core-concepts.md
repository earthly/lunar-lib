# Lunar Core Concepts

This document explains the fundamental concepts, architecture, and execution flow of Earthly Lunar—a guardrails engine for engineering standards enforcement.

## What is Lunar?

Lunar is a **guardrails engine** that automatically enforces engineering standards across an organization's codebase. Instead of broadcasting standards through Slack, email, or Jira tickets, Lunar delivers **contextual feedback directly in pull requests**—exactly where developers can act on it.

## Architecture Overview

**Execution flow:**
- **Collectors** (Bash/Python) gather data and write it to the **Component JSON**
- **Policies** (Python) query the Component JSON and produce **Checks** (pass/fail)

## Key Entities

### Domains

**Domains** are hierarchical groupings that organize related components. They model your organizational structure—products, teams, or systems.

```yaml
domains:
  payments:
    description: Payment processing services
    owner: payments-team@example.com
  payments.api:
    description: Payment API gateway
    owner: api-team@example.com
  payments.processor:
    description: Core payment processor
    owner: processor-team@example.com
```

Key points:
- Domains use dot-notation for hierarchy: `payments.api` is a child of `payments`
- Components in a domain automatically receive the tag `domain:<domain-path>` (e.g., `domain:payments.api`)
- Policies and collectors can target entire domains or specific subdomains

### Components

**Components** are the fundamental units Lunar monitors—typically repositories or directories in a monorepo representing a deployable service or library.

```yaml
components:
  github.com/acme/payment-api:
    owner: jane@example.com
    domain: payments.api
    tags: [go, backend, pci]
    branch: main
    meta:
      pagerduty-policy: P1
  
  # Wildcard matching for monorepos
  github.com/acme/monorepo/*:
    tags: [monorepo]
  
  github.com/acme/monorepo/service-a:
    domain: payments.processor
    tags: [java, tier1]
```

Key points:
- Component names are repository URLs or patterns (wildcards supported)
- Components can have arbitrary tags for targeting collectors and policies
- The `meta` field stores arbitrary key-value metadata
- Components can also be defined in `lunar.yml` files in individual repositories
- Components can also be derived automatically via catalogers (a programmable way to sync information about components and domains from external systems)

### Component JSON

The **Component JSON** is the central data structure in Lunar. It's a JSON document that accumulates all metadata collected about a component. Think of it as a "living document" that represents everything Lunar knows about a service.

```json
{
  "repo": {
    "readme_exists": true,
    "readme_num_lines": 150
  },
  "dockerfile": {
    "images_summary": [
      {"path": "Dockerfile", "images": ["node:18-alpine"]}
    ]
  },
  "k8s": {
    "descriptors": [
      {
        "k8s_file_location": "deploy/deployment.yaml",
        "valid": true,
        "contents": {
          "kind": "Deployment",
          "metadata": {"name": "payment-api"},
          "spec": {"replicas": 3}
        }
      }
    ]
  },
  "coverage": {
    "percentage": 85.5
  }
}
```

Key points:
- The structure is **arbitrary**—collectors define what keys they write to
- Multiple collectors can contribute to different parts of the JSON
- Policies read from this JSON to make pass/fail decisions
- The Component JSON acts as a **contract** between collectors and policies

### Collectors

**Collectors** gather SDLC (Software Development Lifecycle) metadata and write it to the Component JSON. They're triggered by various hooks:

| Hook Type | Trigger | Context |
|-----------|---------|---------|
| `code` | New commits pushed | Lunar Runner (with repo clone) |
| `cron` | Scheduled time | Lunar Runner |
| `ci-before-job` | Before CI job starts | CI Agent (in-pipeline) |
| `ci-after-job` | After CI job completes | CI Agent (in-pipeline) |
| `ci-before-step` | Before CI step | CI Agent (in-pipeline) |
| `ci-after-step` | After CI step | CI Agent (in-pipeline) |
| `ci-before-command` | Before specific command runs | CI Agent (process-level) |
| `ci-after-command` | After specific command runs | CI Agent (process-level) |

Example collector definition:

```yaml
collectors:
  - name: readme
    runBash: |
      if [ -f ./README.md ]; then
        lunar collect -j \
          ".repo.readme_exists" true \
          ".repo.readme_num_lines" "$(wc -l < ./README.md)"
      else
        lunar collect -j ".repo.readme_exists" false
      fi
    on: ["domain:payments"]  # Only runs for components in payments domain
    hook:
      type: code
```

Key points:
- Collectors write "deltas" that get merged into the Component JSON
- The `on` field uses tags to target specific components
- Collectors can be written in Bash (supported) or Python (coming soon)
- CI-based collectors run in the context of the CI pipeline (access to build artifacts, test results, etc.)
- Code/cron collectors run on Lunar Runners with a clone of the repository
- Collectors may run either containerized or non-containerized

### Policies

**Policies** evaluate the Component JSON and produce **checks**—pass/fail assessments of whether a component meets a standard.

```python
from lunar_policy import Check

with Check("readme-exists", "Repository should have a README.md") as c:
    c.assert_true(
        c.get_value(".repo.readme_exists"),
        "README.md file not found"
    )
```

Key points:
- Policies are written in Python using the `lunar_policy` SDK
- Each policy can create one or more checks
- Policies read from the Component JSON using JSONPath-like queries
- Policies have **enforcement levels** that control their impact

### Checks

**Checks** are the individual pass/fail outcomes produced by policies. They represent a single assertion about a component's compliance.

| Status | Meaning |
|--------|---------|
| `pass` | The assertion was satisfied |
| `fail` | The assertion failed—action needed |
| `pending` | Required data not yet available (collector still running) |
| `error` | Policy execution failed (bug in policy code) |

### Enforcement Levels

Policies have enforcement levels that determine their impact:

| Level | Behavior |
|-------|----------|
| `draft` | Hidden from app teams; only visible to platform team for testing |
| `score` | Affects health score in dashboards; not shown in PRs |
| `report-pr` | Shown as comments in PRs; does not block merge |
| `block-pr` | Blocks PR merge until check passes |
| `block-release` | Blocks production deployments (not PRs) |
| `block-pr-and-release` | Blocks both PRs and releases |

This enables **gradual rollout**: start with `draft` → `score` → `report-pr` → `block-pr`.

## Execution Flow

Here's the complete flow when a developer pushes code:

```
1. Developer pushes code to GitHub
           │
           ▼
2. GitHub App detects the push
           │
           ├──────────────────────────────────────┐
           ▼                                      ▼
3a. Code-based collectors run              3b. CI pipeline starts
    on Lunar Runner                             │
           │                                    ▼
           │                            4. CI Agent instruments
           │                               the pipeline
           │                                    │
           │                                    ▼
           │                            5. CI-based collectors run
           │                               at appropriate hooks
           │                                    │
           ▼                                    ▼
6. Collectors write deltas ─────────────▶ Component JSON
   ("lunar collect" command)                    │
                                                ▼
7. Policies evaluate the Component JSON
           │
           ▼
8. Checks are recorded (pass/fail/pending)
           │
           ▼
9. Results posted to PR as status checks
   and/or comments
```

### Partial Results and the Pending Status

Because collectors run asynchronously (some on code push, some during CI), policies must handle **missing data gracefully**:

```python
with Check("coverage-check", "Code coverage should be at least 80%") as c:
    # If .coverage.percentage doesn't exist yet (CI hasn't finished),
    # get_value() raises NoDataError, which becomes status=pending
    coverage = c.get_value(".coverage.percentage")
    c.assert_greater_or_equal(coverage, 80, f"Coverage is {coverage}%, need 80%")
```

The `lunar_policy` SDK automatically:
- Raises `NoDataError` when accessing missing paths (if collectors are still running)
- Converts `NoDataError` to `pending` status
- Re-evaluates the policy when more data arrives

## The lunar-config.yml File

All Lunar configuration is centralized in a single `lunar-config.yml` file, typically stored in its own repository:

```yaml
version: 0

hub:
  host: lunar-hub.internal.example.com
  grpc_port: 9000
  http_port: 8080

domains:
  payments:
    description: Payment processing services
    owner: payments-team@example.com

components:
  github.com/acme/payment-api:
    owner: jane@example.com
    domain: payments
    tags: [go, backend]

collectors:
  - uses: ./collectors/readme
    on: ["domain:payments"]
  - name: inline-collector
    runBash: lunar collect -j ".example" "value"
    on: [backend]
    hook:
      type: code

policies:
  - uses: ./policies/readme
    on: ["domain:payments"]
    enforcement: block-pr
  - name: inline-policy
    runPython: |
      from lunar_policy import Check
      with Check("example", "Example check") as c:
          c.assert_exists(".example")
    on: [backend]
    enforcement: report-pr
```

## Plugin Structure

Both collectors and policies can be packaged as **plugins** (reusable modules):

### Collector Plugin Structure

```
my-collector/
├── lunar-collector.yml    # Plugin configuration
├── main.sh                # Main script (or main.py)
├── Dockerfile             # Optional: used for containerized collectors
├── install.sh             # Optional: install dependencies (non-containerized)
└── requirements.txt       # Optional: Python dependencies (non-containerized)
```

**lunar-collector.yml:**
```yaml
version: 0
name: my-collector
description: Collects XYZ data
author: team@example.com

collectors:
  - name: my-collector
    mainBash: main.sh
    hook:
      type: code

inputs:
  threshold:
    description: The threshold value
    default: "10"
```

### Policy Plugin Structure

```
my-policy/
├── lunar-policy.yml       # Plugin configuration
├── main.py                # Main script
├── Dockerfile             # Optional: used for containerized policies
├── install.sh             # Optional: install dependencies (non-containerized)
└── requirements.txt       # Python dependencies (must include lunar-policy)
```

**lunar-policy.yml:**
```yaml
version: 0
name: my-policy
description: Verifies XYZ requirements
author: team@example.com

policies:
  - mainPython: main.py

inputs:
  min_value:
    description: Minimum required value
    default: "50"
```

## Tagging System

Tags are the mechanism for associating collectors and policies with components:

```yaml
components:
  github.com/acme/api:
    tags: [go, backend, pci, tier1]
    domain: payments

collectors:
  - name: go-linting
    on: [go]           # Runs only for components tagged 'go'
    hook:
      type: code

  - name: pci-scan
    on: [pci]          # Runs only for PCI-tagged components
    hook:
      type: ci-after-job
      pattern: ^build$

policies:
  - name: tier1-coverage
    on: [tier1]        # Applies only to tier1 services
    enforcement: block-pr
```

Components also get automatic tags:
- `domain:<domain-path>` (e.g., `domain:payments.api`)

## Key Concepts Summary

| Concept | Purpose |
|---------|---------|
| **Domain** | Hierarchical grouping of components (org structure) |
| **Component** | A single service/library being monitored |
| **Component JSON** | Accumulated metadata about a component |
| **Collector** | Gathers data and writes to Component JSON |
| **Policy** | Evaluates Component JSON and produces checks |
| **Check** | Individual pass/fail assertion |
| **Hook** | Trigger point for collector execution |
| **Tag** | Label for targeting collectors/policies to components |
| **Enforcement Level** | How strictly a policy affects development workflow |

## Next Steps

- **Collectors**: See [collector-reference.md](./collector-reference.md) for detailed collector documentation
- **Policies**: See [policy-reference.md](./policy-reference.md) for detailed policy documentation
- **Component JSON**: See [component-json-conventions.md](./component-json-conventions.md) for design principles and [component-json-structure.md](./component-json-structure.md) for category structures
