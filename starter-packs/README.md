# Starter Packs

Curated collections of collectors and policies organized by complexity tier. Each pack is a ready-to-use `lunar-config.yml` that you can drop into your project or merge with an existing config.

## Tiers

### [Starter](./starter/) — Zero Config, Zero Secrets

Import and it works. No configuration, no secrets, no vendor accounts. Collectors only trigger when the relevant technology is detected. Five theme-based packs:

- **[Security Essentials](./starter/security-essentials/)** — Vulnerability scanning, secret detection, supply-chain security
- **[Code Quality](./starter/code-quality/)** — Testing, linting, ownership, repo hygiene, language guardrails
- **[Cloud Native](./starter/cloud-native/)** — Kubernetes, Terraform, Docker, IaC security
- **[AI Native](./starter/ai-native/)** — AI instruction files, CLI safety, authorship tracking, code quality gates
- **[Quick Start](./starter/quick-start/)** — Highest-impact items from all categories, minimal noise

All starter packs include every language collector (Go, Java, Node.js, Python, Rust, PHP, C/C++, .NET, HTML/CSS, Shell, Ruby) — they only trigger when the language is detected, so there's zero cost to including them.

### [Starter+](./starter+/) — Light Configuration or Secrets

Easy to set up but requires a secret (API key, token) or a URL to connect to an external service. Examples: Snyk, Jira, SonarQube, PagerDuty.

### [Advanced](./advanced/) — Specific Use Cases or Significant Configuration

For specific use cases or requires meaningful configuration to be useful. Examples: custom AST rules, OpenTelemetry, AI governance, GitOps.

## How to Use

1. Pick a pack from the [Starter](./starter/) tier to get started immediately
2. Copy the `lunar-config.yml` from the pack directory into your project root
3. Customize enforcement levels as your team matures:
   - `score` → track in health dashboard only
   - `report-pr` → comment on PRs without blocking
   - `block-pr` → require passing before merge
4. Use `include`/`exclude` to enable or disable specific checks within a policy
5. Import the same policy multiple times at different enforcement levels for different checks

## Enforcement Level Guide

| Level | PR Comments | Blocks PR | Recommended For |
|-------|-------------|-----------|-----------------|
| `score` | No | No | Getting started, awareness |
| `report-pr` | Yes | No | Visibility without friction |
| `block-pr` | Yes | Yes | Critical checks, mature teams |

## Combining Packs

These packs are starting points. Browse the other packs for ideas and pull in any collectors or policies that fit your needs.
