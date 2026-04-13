# Cloud Native / Infrastructure Starter Pack

For teams running Kubernetes, Terraform, and Docker. Covers resource management, health probes, provider pinning, IaC scanning, and container best practices. All checks skip gracefully when infrastructure files aren't present.

## What's Included

### Collectors
| Collector | Purpose |
|-----------|---------|
| All language collectors | Auto-detect languages, skip if absent |
| `k8s` | Kubernetes manifest analysis (skips if none) |
| `terraform` | Terraform file analysis (skips if none) |
| `docker` | Dockerfile analysis |
| `trivy` | Container + IaC vulnerability scanning (zero-config) |
| `github` | Repo settings |

### Policies

**Kubernetes**
| Policy | Check | Enforcement | Why |
|--------|-------|-------------|-----|
| `k8s` | `requests-and-limits`, `probes` | report-pr | Resource limits and health probes are critical for production |
| `k8s` | `valid`, `pdb`, `non-root`, `min-replicas` | score | Track K8s maturity |

**Terraform**
| Policy | Check | Enforcement | Why |
|--------|-------|-------------|-----|
| `terraform` | `provider-versions-pinned`, `remote-backend` | report-pr | Unpinned providers and local state are operational risks |
| `terraform` | `module-versions-pinned`, `min-provider-versions` | score | Track Terraform hygiene |

**IaC Security**
| Policy | Check | Enforcement | Why |
|--------|-------|-------------|-----|
| `iac` | `valid`, `datastore-destroy-protection` | score | Track IaC standards |
| `iac-scan` | `max-severity` (critical) | report-pr | Surface critical IaC misconfigurations |
| `iac-scan` | `executed` | score | Track scan coverage |

**Containers**
| Policy | Check | Enforcement | Why |
|--------|-------|-------------|-----|
| `container` | `no-latest`, `healthcheck`, `user` | report-pr | Key Dockerfile best practices |
| `container` | `stable-tags`, `build-tagged` | score | Track container hygiene |
| `container-scan` | `max-severity` (critical) | report-pr | Surface critical image vulnerabilities |
| `container-scan` | `executed` | score | Track scan coverage |

**CI**
| Policy | Check | Enforcement | Why |
|--------|-------|-------------|-----|
| `ci` | `lint-clean`, `dependencies-pinned`, `no-mutable-refs` | score | Track CI hygiene |

## Enforcement Philosophy

- **report-pr**: Critical infrastructure checks — missing resource limits, unpinned providers, critical IaC vulnerabilities, Dockerfile security issues
- **score**: Maturity tracking — PodDisruptionBudgets, non-root containers, CI hygiene

## Tightening Over Time

As your infrastructure practices mature, consider promoting:
1. `k8s.non-root` → `report-pr` (once all workloads run as non-root)
2. `terraform.module-versions-pinned` → `report-pr` (once modules are pinned)
3. `container.no-latest` → `block-pr` (once all images use explicit tags)
4. `ci.dependencies-pinned` → `report-pr` (once CI deps are locked)
