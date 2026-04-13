# Security Essentials Starter Pack

For teams whose top priority is vulnerability scanning, secret detection, and supply-chain security.

## What's Included

### Collectors
| Collector | Purpose |
|-----------|---------|
| All language collectors | Only trigger when the language is detected |
| `gitleaks` | Secret scanning (zero-config) |
| `trivy` | SCA + container vulnerability scanning (zero-config) |
| `syft` | SBOM generation (zero-config) |
| `semgrep` | SAST scanning (skips if not configured) |
| `docker` | Dockerfile analysis |
| `github` | Repo settings, branch protection |

### Policies

| Policy | Check | Enforcement | Why |
|--------|-------|-------------|-----|
| `secrets` | `no-hardcoded-secrets` | **block-pr** | Leaked secrets must never merge |
| `secrets` | `executed` | score | Track that scanner ran |
| `sca` | `max-severity` (critical) | report-pr | Surface critical vulns on PRs |
| `sca` | `executed` | score | Track SCA coverage |
| `sast` | `max-severity` (high) | report-pr | Surface high-severity findings |
| `sast` | `executed` | score | Track SAST coverage |
| `container-scan` | `max-severity` (critical) | report-pr | Surface critical image vulns |
| `container-scan` | `executed` | score | Track scan coverage |
| `container` | `no-latest`, `user` | report-pr | No `:latest` tags, non-root containers |
| `container` | `healthcheck`, `stable-tags` | score | Track Dockerfile best practices |
| `sbom` | `sbom-exists`, `has-licenses` | score | Track SBOM generation |
| `vcs` | `branch-protection-enabled`, `require-pull-request` | report-pr | Surface missing branch protection |
| `vcs` | `minimum-approvals`, `require-codeowner-review`, `disallow-force-push` | score | Track VCS maturity |

## Enforcement Philosophy

- **block-pr**: Only secret detection — leaked secrets are an immediate security incident
- **report-pr**: Vulnerability findings and critical Dockerfile issues — visible on every PR but won't block while your team ramps up
- **score**: Everything else — tracked in your health dashboard for gradual improvement

## Tightening Over Time

As your team matures, consider promoting:
1. `sca.max-severity` → `block-pr` (once your dependency hygiene is clean)
2. `container.no-latest` → `block-pr` (once all images use explicit tags)
3. `vcs.branch-protection-enabled` → `block-pr` (once all repos have protection)
