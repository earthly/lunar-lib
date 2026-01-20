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

**Important**: Do not read all specs at once! Read only select files, and only in small chunks, as needed. Avoid reading all of them as that is too much information to process at once.

If you need to find a specific spec, you can grep these files for the guardrail identifier.

How to implement a guardrail:

1. **Pick a guardrail** from any spec file (or grep for one based on the guardrail identifier)
2. **Read the ai-context docs** for implementation details:
   - [about-lunar.md](../about-lunar.md) — what Lunar is and how it works
   - [core-concepts.md](../core-concepts.md) — core concepts
   - [collector-reference.md](../collector-reference.md) — how to write collectors
   - [policy-reference.md](../policy-reference.md) — how to write policies
   - [strategies.md](../strategies.md) — implementation strategies
   - [component-json-conventions.md](../component-json-conventions.md) — schema design
   - [component-json-reference.md](../component-json-reference.md) — schema reference
3. **Implement** the collector(s) and policy following the spec
