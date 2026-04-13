# Quick Start Pack

The "just works" pack — highest-impact items from security, quality, and infrastructure with zero noise. Almost everything runs at `score` level (health dashboard only), with one exception: secret detection reports on PRs because leaked secrets are an emergency, not a gradual improvement.

## What's Included

### Collectors
| Collector | Purpose |
|-----------|---------|
| All language collectors | Only trigger when the language is detected |
| `readme` | README analysis |
| `codeowners` | CODEOWNERS parsing |
| `repo-boilerplate` | Standard repo files |
| `github` | Repo settings |
| `gitleaks` | Secret scanning (zero-config) |
| `trivy` | Dependency vulnerability scanning (zero-config) |
| `syft` | SBOM generation (zero-config) |
| `docker` | Dockerfile analysis (skips if none) |

### Policies

| Policy | Check | Enforcement | Category |
|--------|-------|-------------|----------|
| `secrets` | `no-hardcoded-secrets` | **report-pr** | Security |
| `repo-boilerplate` | `readme-exists`, `codeowners-exists`, `gitignore-exists`, `license-exists` | score | Quality |
| `codeowners` | `exists`, `valid` | score | Quality |
| `vcs` | `branch-protection-enabled`, `require-pull-request` | score | Security |
| `testing` | `executed`, `passing` | score | Quality |
| `linter` | `ran` | score | Quality |
| `dependencies` | `min-versions` | score | Quality |
| `sca` | `executed`, `max-severity` (critical) | score | Security |
| `sbom` | `sbom-exists` | score | Security |
| `container` | `no-latest`, `user`, `healthcheck`, `dockerfile-lint-clean` | score | Infrastructure |

## Enforcement Philosophy

- **report-pr**: Secret detection only — the one check where immediate visibility matters
- **score**: Everything else — gives your team a health dashboard baseline without any PR friction

This pack is designed for day-one adoption. Import it, look at your dashboard, and decide which checks to promote to `report-pr` or `block-pr` based on what matters most to your team.

## Growing From Here

Once you're comfortable with the Quick Start baseline:

1. **Want more security?** Switch to the [Security Essentials](../security-essentials/) pack or promote `sca.max-severity` and `vcs.branch-protection-enabled` to `report-pr`
2. **Want language guardrails?** Switch to the [Code Quality](../code-quality/) pack or add language-specific policies
3. **Running K8s/Terraform?** Switch to the [Cloud Native](../cloud-native/) pack or add `k8s` and `terraform` policies
4. **Want it all?** Combine packs by merging their configs
