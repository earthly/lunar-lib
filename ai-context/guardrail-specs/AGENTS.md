# Guardrail Specifications

This directory contains detailed specifications for 500+ Lunar guardrails organized by category.

## Purpose

These specs define **what** guardrails to build—each entry includes:
- Summary and detailed description
- Collector requirements (what data to collect)
- Component JSON paths (where data lives)
- Policy logic (what to check)
- Configuration parameters (tunable thresholds)

## Files

| File | Coverage |
|------|----------|
| `deployment-and-infrastructure.md` | K8s, IaC (Terraform), containers, CD pipelines, database schemas |
| `security-and-compliance.md` | Vulnerability scanning, secrets, compliance regimes, access control |
| `testing-and-quality.md` | Unit/integration tests, coverage, performance, test quality |
| `devex-build-and-ci.md` | Golden paths, dependencies, images, artifacts, build standards |
| `repository-and-ownership.md` | README, CODEOWNERS, catalog, branch protection, standard files |
| `operational-readiness.md` | On-call, runbooks, observability, alerting, DR, capacity |

## Usage

1. **Pick a guardrail** from any spec file
2. **Read the ai-context docs** for implementation details:
   - [collector-reference.md](../collector-reference.md) — how to write collectors
   - [policy-reference.md](../policy-reference.md) — how to write policies
   - [component-json-conventions.md](../component-json-conventions.md) — schema design
3. **Implement** the collector(s) and policy following the spec
