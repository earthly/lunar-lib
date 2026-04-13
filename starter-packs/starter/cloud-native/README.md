# Cloud Native / Infrastructure Starter Pack

For teams running Kubernetes, Terraform, and Docker. Covers resource management, health probes, provider pinning, IaC scanning, and container best practices. Checks only trigger when the relevant infrastructure files are present.

## What's Included

### Collectors
| Collector | Purpose |
|-----------|---------|
| All language collectors | Only trigger when the language is detected |
| `k8s` | Kubernetes manifest analysis (skips if none) |
| `terraform` | Terraform file analysis (skips if none) |
| `docker` | Dockerfile analysis |
| `trivy` | Dependency vulnerability scanning (zero-config) |
| `checkov` | IaC scanning (zero-config) |
| `github` | Repo settings |

### Policies

| Policy | Check | Enforcement | Why |
|--------|-------|-------------|-----|
| `container` | `no-latest` | **report-pr** | Using `:latest` tags is the clearest anti-pattern |
| `container` | `healthcheck`, `user`, `stable-tags`, `build-tagged`, `dockerfile-lint-clean` | score | Track Dockerfile maturity |
| `k8s` | `requests-and-limits`, `probes`, `valid`, `pdb`, `non-root`, `min-replicas` | score | Track K8s maturity |
| `terraform` | `provider-versions-pinned`, `remote-backend`, `module-versions-pinned`, `min-provider-versions` | score | Track Terraform hygiene |
| `iac` | `valid`, `datastore-destroy-protection` | score | Track IaC standards |
| `iac-scan` | `executed`, `max-severity` (critical) | score | Track IaC security |
| `container-scan` | `executed`, `max-severity` (critical) | score | Track container security |
| `ci` | `lint-clean`, `dependencies-pinned`, `no-mutable-refs` | score | Track CI hygiene |

## Enforcement Philosophy

- **report-pr**: Only `container.no-latest` — the single clearest day-1 anti-pattern
- **score**: Everything else — gives your team a health dashboard baseline without PR friction on day 1

## Tightening Over Time

As your infrastructure practices mature, consider promoting:
1. `k8s.requests-and-limits` → `report-pr` (once all workloads have limits)
2. `terraform.provider-versions-pinned` → `report-pr` (once providers are pinned)
3. `container.no-latest` → `block-pr` (once all images use explicit tags)
4. `iac-scan.max-severity` → `report-pr` (once critical IaC issues are resolved)
