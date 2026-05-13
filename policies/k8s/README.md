# Kubernetes Guardrails

Enforces Kubernetes best practices for production-ready workloads.

## Overview

This policy validates Kubernetes manifests against industry best practices including resource limits, health probes, PodDisruptionBudgets, and security configurations. It helps ensure your K8s workloads are production-ready and resilient.

## Policies

This policy provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|-----------|-------------|-----------------|
| `valid` | Validates K8s manifest syntax | Manifest has YAML or schema errors |
| `requests-and-limits` | Checks CPU/memory requests and limits | Container missing resource specs |
| `probes` | Requires liveness and readiness probes | Container missing health probes |
| `min-replicas` | Enforces minimum HPA replicas | HPA minReplicas below threshold |
| `pdb` | Requires PodDisruptionBudgets | Deployment/StatefulSet missing PDB |
| `non-root` | Requires non-root security context | Container may run as root |
| `host-users` | Requires PodSpecs to set `hostUsers: false` (K8s ≥1.36 user namespaces) | Container UIDs are not isolated from host UIDs — a container escape gives the attacker root on the node |
| `host-network` | Forbids `hostNetwork: true` on PodSpecs | Workload shares the host network namespace — bypasses NetworkPolicy and exposes node interfaces |
| `host-pid` | Forbids `hostPID: true` on PodSpecs | Workload shares the host PID namespace — can see, signal, and potentially attach to processes on the node |
| `host-ipc` | Forbids `hostIPC: true` on PodSpecs | Workload shares the host IPC namespace — can read or tamper with node-wide shared memory |
| `min-kubectl-version` | Enforces minimum kubectl version in CI | kubectl client used in CI is below threshold |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.k8s.manifests[]` | array | `k8s` collector |
| `.k8s.workloads[]` | array | `k8s` collector |
| `.k8s.hpas[]` | array | `k8s` collector |
| `.k8s.pdbs[]` | array | `k8s` collector |
| `.k8s.cicd.cmds[]` | array | `k8s` collector (cicd sub-collector) |

**Note:** Ensure the `k8s` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/k8s@v1.0.0
    on: [kubernetes]

policies:
  - uses: github://earthly/lunar-lib/policies/k8s@v1.0.0
    on: [kubernetes]
    enforcement: report-pr
    # include: [valid, requests-and-limits, probes]  # Only run specific checks
    # with:
    #   min_replicas: "3"
    #   max_limit_to_request_ratio: "4"
    #   min_kubectl_version: "1.28"
```

## Examples

### Passing Example

A compliant component with proper resource specs, probes, and security context:

```json
{
  "k8s": {
    "manifests": [
      {"path": "deploy/deployment.yaml", "valid": true}
    ],
    "workloads": [
      {
        "kind": "Deployment",
        "name": "payment-api",
        "namespace": "payments",
        "path": "deploy/deployment.yaml",
        "host_users": false,
        "host_network": false,
        "host_pid": false,
        "host_ipc": false,
        "containers": [
          {
            "name": "api",
            "has_resources": true,
            "has_requests": true,
            "has_limits": true,
            "has_liveness_probe": true,
            "has_readiness_probe": true,
            "runs_as_non_root": true
          }
        ]
      }
    ],
    "pdbs": [
      {"name": "payment-api-pdb", "target_workload": "payment-api"}
    ]
  }
}
```

### Failing Example

A component missing resources, probes, and security configuration:

```json
{
  "k8s": {
    "workloads": [
      {
        "kind": "Deployment",
        "name": "my-app",
        "namespace": "default",
        "path": "deploy/app.yaml",
        "host_users": true,
        "host_network": true,
        "host_pid": true,
        "host_ipc": true,
        "containers": [
          {
            "name": "app",
            "has_resources": false,
            "has_requests": false,
            "has_limits": false,
            "has_liveness_probe": false,
            "has_readiness_probe": false,
            "runs_as_non_root": false
          }
        ]
      }
    ],
    "pdbs": []
  }
}
```

**Failure messages:**
- `deploy/app.yaml: Deployment default/my-app container 'app' missing resource requests`
- `deploy/app.yaml: Deployment default/my-app container 'app' missing livenessProbe`
- `deploy/app.yaml: Deployment default/my-app container 'app' should set securityContext.runAsNonRoot: true`
- `deploy/app.yaml: Deployment default/my-app should set spec.hostUsers: false (Kubernetes user namespaces, GA in v1.36)`
- `deploy/app.yaml: Deployment default/my-app should not set spec.hostNetwork: true (workload shares the host network namespace)`
- `deploy/app.yaml: Deployment default/my-app should not set spec.hostPID: true (workload shares the host PID namespace)`
- `deploy/app.yaml: Deployment default/my-app should not set spec.hostIPC: true (workload shares the host IPC namespace)`

## Remediation

When this policy fails, resolve it by:

1. **For `valid` failures:** Fix YAML syntax errors or invalid K8s fields in the manifest
2. **For `requests-and-limits` failures:** Add `resources.requests` and `resources.limits` for CPU and memory
3. **For `probes` failures:** Add `livenessProbe` and `readinessProbe` to each container
4. **For `min-replicas` failures:** Increase `spec.minReplicas` in your HPA to meet the threshold
5. **For `pdb` failures:** Create a PodDisruptionBudget that selects your workload's pods
6. **For `non-root` failures:** Add `securityContext.runAsNonRoot: true` to the container or pod spec
7. **For `host-users` failures:** Add `spec.hostUsers: false` to the PodSpec (or `spec.template.spec.hostUsers: false` for Deployments/StatefulSets/DaemonSets/Jobs/CronJobs). Requires Kubernetes ≥1.36 in the target cluster. Privileged workloads that must share the host user namespace (e.g. log shippers reading host paths, kubelets, container-runtime sidecars) can use `include`/`exclude` in `lunar-config.yml` to opt out.
8. **For `host-network` failures:** Remove `spec.hostNetwork: true` from the PodSpec. Workloads that legitimately need the host network (CNI agents, node-local proxies, host-bound metrics exporters) can opt out via `include`/`exclude` in `lunar-config.yml`.
9. **For `host-pid` failures:** Remove `spec.hostPID: true` from the PodSpec. Node-level monitoring agents that need a host-wide process view can opt out via `include`/`exclude` in `lunar-config.yml`.
10. **For `host-ipc` failures:** Remove `spec.hostIPC: true` from the PodSpec. Workloads that genuinely need host IPC (rare — usually legacy shared-memory consumers) can opt out via `include`/`exclude` in `lunar-config.yml`.
11. **For `min-kubectl-version` failures:** Upgrade the kubectl client in your CI pipeline (e.g., pin `azure/setup-kubectl@v4` or `setup-kubectl` action to a newer version, or update the installed kubectl on self-hosted runners)

Consumers who want any of these surfaced without blocking can pin `enforcement: report-pr` at config time — but that's a consumer-side knob; the checks themselves just pass or fail.

