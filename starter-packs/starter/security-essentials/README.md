# Security Essentials Starter Pack

For teams whose top priority is vulnerability scanning, secret detection, and supply-chain security.

## What's Included

### Collectors
| Collector | Purpose |
|-----------|---------|
| All language collectors | Only trigger when the language is detected |
| `gitleaks` | Secret scanning (zero-config) |
| `trivy` | Dependency vulnerability scanning (zero-config) |
| `syft` | SBOM generation (zero-config) |
| `semgrep` | SAST scanning (skips if not configured) |
| `snyk` | Snyk security scanning (skips if not configured) |
| `codeql` | CodeQL static analysis (skips if not configured) |
| `docker` | Dockerfile analysis |
| `github` | Repo settings, branch protection |
| `github-actions` | GitHub Actions workflow analysis |

### Policies

| Policy | Check | Enforcement | Why |
|--------|-------|-------------|-----|
| `secrets` | `no-hardcoded-secrets` | **block-pr** | Leaked secrets must never merge |
| `secrets` | `executed` | score | Track that scanner ran |
| `sca` | `executed`, `max-severity` (critical) | score | Track SCA coverage |
| `sast` | `executed`, `max-severity` (high) | score | Track SAST coverage |
| `container-scan` | `executed`, `max-severity` (critical) | score | Track container security |
| `github-actions` | `no-script-injection`, `no-dangerous-trigger-checkout`, `permissions-declared`, `no-write-all-permissions`, `checkout-no-persist-credentials`, `no-secrets-inherit` | score | Track CI/CD security |
| `container` | `no-latest`, `user`, `healthcheck`, `stable-tags`, `dockerfile-lint-clean` | score | Track Dockerfile maturity |
| `sbom` | `sbom-exists`, `has-licenses` | score | Track SBOM generation |
| `vcs` | `branch-protection-enabled`, `require-pull-request`, `minimum-approvals`, `require-codeowner-review`, `disallow-force-push` | score | Track VCS maturity |

## Enforcement Philosophy

- **block-pr**: Only secret detection — leaked secrets are an immediate security incident
- **score**: Everything else — gives your team a security health dashboard without PR friction on day 1

## Tightening Over Time

As your security posture matures, consider promoting:
1. `sca.max-severity` → `report-pr` (once your dependency hygiene is clean)
2. `container.no-latest` → `report-pr` (once all images use explicit tags)
3. `vcs.branch-protection-enabled` → `report-pr` (once all repos have protection)
4. `sast.max-severity` → `report-pr` (once existing findings are triaged)
