# Kubernetes Guardrails

Enforces Kubernetes best practices for production-ready workloads.

## Overview

This policy validates Kubernetes manifests against industry best practices including resource limits, health probes, PodDisruptionBudgets, and security configurations. It helps ensure your K8s workloads are production-ready and resilient.

## Policies

This policy provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|-----------|-------------|-----------------|
| `valid` | Validates K8s manifest syntax | Manifest has YAML or schema errors |
| `resources` | Checks CPU/memory requests and limits | Container missing resource specs |
| `probes` | Requires liveness and readiness probes | Container missing health probes |
| `min-replicas` | Enforces minimum HPA replicas | HPA minReplicas below threshold |
| `pdb` | Requires PodDisruptionBudgets | Deployment/StatefulSet missing PDB |
| `non-root` | Requires non-root security context | Container may run as root |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.k8s.manifests[]` | array | `k8s` collector |
| `.k8s.workloads[]` | array | `k8s` collector |
| `.k8s.hpas[]` | array | `k8s` collector |
| `.k8s.pdbs[]` | array | `k8s` collector |

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
    # include: [valid, resources, probes]  # Only run specific checks
    # with:
    #   min_replicas: "3"
    #   max_limit_to_request_ratio: "4"
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

## Remediation

When this policy fails, resolve it by:

1. **For `valid` failures:** Fix YAML syntax errors or invalid K8s fields in the manifest
2. **For `resources` failures:** Add `resources.requests` and `resources.limits` for CPU and memory
3. **For `probes` failures:** Add `livenessProbe` and `readinessProbe` to each container
4. **For `min-replicas` failures:** Increase `spec.minReplicas` in your HPA to meet the threshold
5. **For `pdb` failures:** Create a PodDisruptionBudget that selects your workload's pods
6. **For `non-root` failures:** Add `securityContext.runAsNonRoot: true` to the container or pod spec

