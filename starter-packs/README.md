# Starter Packs

Curated collections of collectors and policies for common use cases. Each pack is a ready-to-use `lunar-config.yml` that you can drop into your project or merge with an existing config.

All packs include every language collector (Go, Java, Node.js, Python, Rust, PHP, C/C++, .NET, HTML/CSS) — they skip automatically when the language isn't detected, so there's zero cost to including them.

## Available Packs

### [Security Essentials](./security-essentials/)
For teams whose top priority is vulnerability scanning, secret detection, and supply-chain security. Includes scanners (Gitleaks, Trivy, Syft, Semgrep), container security, and VCS branch protection. Critical checks like secret detection block PRs; scanning tools report for awareness.

### [Code Quality](./code-quality/)
For teams focused on testing, linting, code ownership, and repo hygiene. Includes repo standards (README, CODEOWNERS, license), testing and linter enforcement, dependency management, and language-specific guardrails for every detected language.

### [Cloud Native](./cloud-native/)
For teams running Kubernetes, Terraform, and Docker. Covers resource limits, health probes, provider pinning, IaC scanning, Dockerfile best practices, and container vulnerability scanning. All checks skip gracefully when infrastructure files aren't present.

### [Quick Start](./quick-start/)
The "just works" pack — highest-impact items from all categories with minimal noise. Everything runs at `score` level (no PR blocking) except secret detection, which reports on PRs. Perfect for teams that want immediate visibility without disruption.

## How to Use

1. Copy the `lunar-config.yml` from the pack directory into your project root
2. Customize enforcement levels as your team matures:
   - `score` → track in health dashboard only
   - `report-pr` → comment on PRs without blocking
   - `block-pr` → require passing before merge
3. Use `include`/`exclude` to enable or disable specific checks within a policy
4. Import the same policy multiple times at different enforcement levels for different checks

## Enforcement Level Guide

| Level | PR Comments | Blocks PR | Recommended For |
|-------|-------------|-----------|-----------------|
| `score` | No | No | Getting started, awareness |
| `report-pr` | Yes | No | Visibility without friction |
| `block-pr` | Yes | Yes | Critical checks, mature teams |

## Combining Packs

Packs can be combined by merging their `lunar-config.yml` files. When the same policy appears in multiple packs, keep the entry with the higher enforcement level or merge their `include` lists.
