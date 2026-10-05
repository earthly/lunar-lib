# Kubernetes Guardrails

Enforces Kubernetes best practices for production-ready workloads.

## Overview

This policy validates Kubernetes manifests against industry best practices including resource limits, health probes, PodDisruptionBudgets, autoscaling, topology spread, graceful shutdown, and security configurations. It evaluates plain manifests and rendered Helm charts alike, so chart-based workloads are held to the same standard. It helps ensure your K8s workloads are production-ready and resilient.

## Policies

This policy provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|-----------|-------------|-----------------|
| `valid` | Validates K8s manifest syntax, and that Helm charts render | Manifest has YAML or schema errors, or a chart fails to render |
| `requests-and-limits` | Checks CPU/memory requests and limits | Container missing resource specs |
| `probes` | Requires liveness and readiness probes | Container missing health probes |
| `min-replicas` | Enforces minimum HPA replicas | HPA minReplicas below threshold |
| `pdb` | Requires PodDisruptionBudgets | Deployment/StatefulSet missing PDB |
| `non-root` | Requires non-root security context | Container may run as root |
| `host-users` | Requires PodSpecs to set `hostUsers: false` (K8s ≥1.36 user namespaces) | Container UIDs are not isolated from host UIDs — a container escape gives the attacker root on the node |
| `host-network` | Forbids `hostNetwork: true` on PodSpecs | Workload shares the host network namespace — bypasses NetworkPolicy and exposes node interfaces |
| `host-pid` | Forbids `hostPID: true` on PodSpecs | Workload shares the host PID namespace — can see, signal, and potentially attach to processes on the node |
| `host-ipc` | Forbids `hostIPC: true` on PodSpecs | Workload shares the host IPC namespace — can read or tamper with node-wide shared memory |
| `metadata-egress-blocked` | Requires NetworkPolicy to block pod egress to the instance-metadata endpoint | Workload's pods can reach 169.254.169.254, where node credentials can be read |
| `min-kubectl-version` | Enforces minimum kubectl version in CI | kubectl client used in CI is below threshold |
| `topology-spread` | Requires a topologySpreadConstraint on `topology_key` (zone by default) for Deployments and StatefulSets that can run more than one replica (see [Replica counts](#replica-counts)) | Replicas can all land in one zone, so one zone failure takes the workload down |
| `graceful-shutdown` | Requires a preStop hook and a long enough termination grace period on Deployments and StatefulSets | Pods stop while requests are still in flight or still being routed to them |
| `pdb-budget` | Requires every PodDisruptionBudget to allow at least one voluntary disruption at the smallest size of the workloads it covers (see [Replica counts](#replica-counts)) | The budget blocks node drains, so nodes can't be upgraded or patched |
| `no-static-replicas` | Forbids `spec.replicas` on a workload an HPA or KEDA ScaledObject scales | Every deploy resets the replica count the autoscaler chose |
| `probes-distinct` | Requires liveness and readiness probes to check different endpoints | An overloaded pod is restarted instead of taken out of rotation |
| `probe-timeouts` | Requires probe timeouts of at least `min_probe_timeout_seconds` and below the probe period | Slow responses fail probes, or a check is still running when the next one starts |
| `allowed-registries` | Restricts container and init container images to `allowed_registries` (opt-in) | Workload pulls an image from an unapproved registry |
| `deprecated-api-versions` | Forbids the apiVersions in `deprecated_api_versions` (opt-in) | Manifest uses an API that is deprecated or removed on the target clusters |
| `pod-annotations` | Enforces `required_pod_annotations` and `forbidden_pod_annotations` on pod templates (opt-in) | Pod template is missing a required annotation or sets a forbidden one |

### Helm charts

The `k8s` collector's `helm` sub-collector renders each chart and records the objects with a `render` key: the chart directory and the values files used. Every check covers those objects like plain manifests, with these differences:

- A failure names the chart template and the values files, e.g. `charts/api/templates/deployment.yaml [values-prod.yaml]: ...`. When the same finding shows up in several values sets of a chart, it's reported once and lists them.
- A workload is never matched to a PodDisruptionBudget, autoscaler or NetworkPolicy from another values set of its own chart, since those are alternative deployments of the same release. Objects from the same render, from plain manifests and from other charts all match, so a plain-manifest workload can be covered by a chart's PodDisruptionBudget.
- A chart that fails to render fails `valid` with helm's error, so it can't pass every other check by contributing nothing.
- A chart that no `helm_values` line or `helm_values_chains` chain applies to is only checked by `valid`: its default render contributes no objects, because chart defaults (`resources: {}`, a disabled PodDisruptionBudget) are often left for whoever deploys the chart to fill in. When such charts are a component's only Kubernetes content, the workload checks skip and say that no values set applies, pointing at `helm_values` and `helm_values_chains`.

The checks added alongside chart rendering (`topology-spread` through `pod-annotations`) skip when the `k8s` collector is older than the fields they read, and when nothing in the repository is in their scope, such as no workload that can run more than one replica, rather than passing on nothing.

### Replica counts

A workload that an HPA or KEDA ScaledObject scales gets its size from the autoscaler, matched by `scaleTargetRef` in the same namespace (and under the render rules above), since `no-static-replicas` asks for `spec.replicas` to be left out. `pdb-budget` uses its smallest size, the autoscaler's minimum (`minReplicas` / `minReplicaCount`, at least 1), and `topology-spread` its largest (`maxReplicas` / `maxReplicaCount`). A workload without one uses `spec.replicas`, or 1 when it's unset. Percentages round up against that count, as Kubernetes' disruption controller does: `minAvailable: 50%` of 3 pods leaves one free and passes, `67%` of 3 covers all of them and fails, and only `maxUnavailable: 0` or `0%` blocks every drain. A budget that selects several workloads counts their pods together, as Kubernetes does.

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.k8s.manifests[]` | array | `k8s` collector (`k8s` and `helm` sub-collectors) |
| `.k8s.workloads[]` | array | `k8s` collector (`k8s` and `helm` sub-collectors) |
| `.k8s.hpas[]` | array | `k8s` collector (`k8s` and `helm` sub-collectors) |
| `.k8s.scaled_objects[]` | array | `k8s` collector (`k8s` and `helm` sub-collectors) |
| `.k8s.pdbs[]` | array | `k8s` collector (`k8s` and `helm` sub-collectors) |
| `.k8s.network_policies[]` | array | `k8s` collector (`k8s` and `helm` sub-collectors) |
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
    #   metadata_ips: "169.254.169.254,fd00:ec2::254"  # IPv6 EKS clusters
    #   topology_key: "topology.kubernetes.io/zone"
    #   topology_max_skew: "1"
    #   topology_when_unsatisfiable: "ScheduleAnyway"
    #   min_termination_grace_period_seconds: "60"
    #   min_probe_timeout_seconds: "2"
    #   allowed_registries: "ghcr.io/acme,123456789012.dkr.ecr.us-east-1.amazonaws.com"
    #   deprecated_api_versions: "policy/v1beta1,autoscaling/v2beta2"
    #   required_pod_annotations: "prometheus.io/scrape"
    #   forbidden_pod_annotations: "karpenter.sh/do-not-disrupt"
```

## Examples

### Passing Example

A compliant component with proper resource specs, probes, spread, shutdown handling, and security context:

```json
{
  "k8s": {
    "manifests": [
      {"path": "deploy/deployment.yaml", "valid": true, "resources": [
        {"kind": "Deployment", "name": "payment-api", "namespace": "payments", "api_version": "apps/v1"}
      ]}
    ],
    "workloads": [
      {
        "kind": "Deployment",
        "name": "payment-api",
        "namespace": "payments",
        "path": "deploy/deployment.yaml",
        "replicas": 3,
        "replicas_set": true,
        "pod_labels": {"app": "payment-api"},
        "pod_annotations": {},
        "host_users": false,
        "host_network": false,
        "host_pid": false,
        "host_ipc": false,
        "termination_grace_period_seconds": 60,
        "topology_spread_constraints": [
          {"topology_key": "topology.kubernetes.io/zone", "max_skew": 1, "when_unsatisfiable": "ScheduleAnyway", "label_selector": {"matchLabels": {"app": "payment-api"}}, "match_label_keys": ["pod-template-hash"]}
        ],
        "containers": [
          {
            "name": "api",
            "image": "gcr.io/acme/payment-api:v1.2.3",
            "has_resources": true,
            "has_requests": true,
            "has_limits": true,
            "has_liveness_probe": true,
            "has_readiness_probe": true,
            "liveness_probe": {"handler": "httpGet", "port": 8080, "path": "/livez", "period_seconds": 10, "timeout_seconds": 2},
            "readiness_probe": {"handler": "httpGet", "port": 8080, "path": "/readyz", "period_seconds": 5, "timeout_seconds": 2},
            "has_prestop": true,
            "runs_as_non_root": true
          }
        ],
        "init_containers": []
      }
    ],
    "pdbs": [
      {"name": "payment-api-pdb", "namespace": "payments", "selector": {"matchLabels": {"app": "payment-api"}}, "min_available": null, "max_unavailable": 1}
    ],
    "network_policies": [
      {
        "name": "egress-no-metadata",
        "namespace": "payments",
        "pod_selector": {},
        "policy_types": ["Egress"],
        "egress": [{"to": [{"ipBlock": {"cidr": "0.0.0.0/0", "except": ["169.254.169.254/32"]}}]}]
      }
    ]
  }
}
```

### Failing Example

A Helm chart rendered with `values-prod.yaml`, plus a second chart whose dependencies aren't vendored:

```json
{
  "k8s": {
    "manifests": [
      {"path": "charts/my-app", "render": {"chart": "charts/my-app", "values": ["values.yaml", "values-prod.yaml"], "validated_only": false}, "valid": true, "resources": [
        {"kind": "Deployment", "name": "my-app", "namespace": "default", "api_version": "apps/v1"}
      ]},
      {"path": "charts/reports", "render": {"chart": "charts/reports", "values": ["values.yaml"], "validated_only": true}, "valid": false,
       "error": "helm template: An error occurred while checking for chart dependencies. You may need to run `helm dependency build` to fetch missing dependencies: found in Chart.yaml, but missing in charts/ directory: postgresql"}
    ],
    "workloads": [
      {
        "kind": "Deployment",
        "name": "my-app",
        "namespace": "default",
        "path": "charts/my-app/templates/deployment.yaml",
        "render": {"chart": "charts/my-app", "values": ["values.yaml", "values-prod.yaml"]},
        "replicas": 2,
        "replicas_set": true,
        "pod_labels": {"app": "my-app"},
        "pod_annotations": {"karpenter.sh/do-not-disrupt": "true"},
        "host_users": true,
        "host_network": true,
        "host_pid": true,
        "host_ipc": true,
        "termination_grace_period_seconds": 30,
        "topology_spread_constraints": [],
        "containers": [
          {
            "name": "app",
            "image": "nginx:1.25",
            "has_resources": false,
            "has_requests": false,
            "has_limits": false,
            "has_liveness_probe": true,
            "has_readiness_probe": true,
            "liveness_probe": {"handler": "httpGet", "port": 8080, "path": "/healthz", "period_seconds": 10, "timeout_seconds": 10},
            "readiness_probe": {"handler": "httpGet", "port": 8080, "path": "/healthz", "period_seconds": 10, "timeout_seconds": 1},
            "has_prestop": false,
            "runs_as_non_root": false
          }
        ],
        "init_containers": []
      }
    ],
    "pdbs": [
      {"name": "my-app", "namespace": "default", "path": "charts/my-app/templates/pdb.yaml", "render": {"chart": "charts/my-app", "values": ["values.yaml", "values-prod.yaml"]},
       "selector": {"matchLabels": {"app": "my-app"}}, "min_available": 2, "max_unavailable": null}
    ],
    "hpas": [
      {"name": "my-app", "namespace": "default", "path": "charts/my-app/templates/hpa.yaml", "render": {"chart": "charts/my-app", "values": ["values.yaml", "values-prod.yaml"]},
       "target_workload": "my-app", "min_replicas": 2, "max_replicas": 6}
    ]
  }
}
```

**Failure messages** (`allowed-registries` with `allowed_registries: "ghcr.io/acme"`, `pod-annotations` with `forbidden_pod_annotations: "karpenter.sh/do-not-disrupt"`):
- `charts/reports [values.yaml]: helm template: An error occurred while checking for chart dependencies. ... missing in charts/ directory: postgresql`
- `charts/my-app/templates/deployment.yaml [values-prod.yaml]: Deployment default/my-app container 'app' missing resource requests`
- `charts/my-app/templates/deployment.yaml [values-prod.yaml]: Deployment default/my-app container 'app' should set securityContext.runAsNonRoot: true`
- `charts/my-app/templates/deployment.yaml [values-prod.yaml]: Deployment default/my-app should not set spec.hostNetwork: true (workload shares the host network namespace)`
- `charts/my-app/templates/hpa.yaml [values-prod.yaml]: HPA default/my-app has minReplicas=2, need at least 3`
- `charts/my-app/templates/deployment.yaml [values-prod.yaml]: Deployment default/my-app has no topologySpreadConstraint on topology.kubernetes.io/zone`
- `charts/my-app/templates/deployment.yaml [values-prod.yaml]: Deployment default/my-app has no container with a preStop hook`
- `charts/my-app/templates/pdb.yaml [values-prod.yaml]: PodDisruptionBudget default/my-app allows no voluntary disruptions: minAvailable 2 covers Deployment my-app, which runs at least 2 replicas`
- `charts/my-app/templates/deployment.yaml [values-prod.yaml]: Deployment default/my-app sets spec.replicas: 2 while HorizontalPodAutoscaler my-app scales it`
- `charts/my-app/templates/deployment.yaml [values-prod.yaml]: Deployment default/my-app container 'app' livenessProbe and readinessProbe both check httpGet :8080/healthz`
- `charts/my-app/templates/deployment.yaml [values-prod.yaml]: Deployment default/my-app container 'app' livenessProbe timeoutSeconds 10 is not below periodSeconds 10`
- `charts/my-app/templates/deployment.yaml [values-prod.yaml]: Deployment default/my-app container 'app' image nginx:1.25 (docker.io/library/nginx) is not from an allowed registry`
- `charts/my-app/templates/deployment.yaml [values-prod.yaml]: Deployment default/my-app pod template sets forbidden annotation karpenter.sh/do-not-disrupt`

## Remediation

When this policy fails, resolve it by:

1. **For `valid` failures:** Fix YAML syntax errors or invalid K8s fields in the manifest. For a chart that fails to render, fix the error helm reports: vendor missing dependencies into the chart's `charts/` directory (or set the collector's `helm_dependency_build: true`), and point `helm_values` at the values files the chart needs
2. **For `requests-and-limits` failures:** Add `resources.requests` and `resources.limits` for CPU and memory
3. **For `probes` failures:** Add `livenessProbe` and `readinessProbe` to each container
4. **For `min-replicas` failures:** Increase `spec.minReplicas` in your HPA to meet the threshold
5. **For `pdb` failures:** Create a PodDisruptionBudget that selects your workload's pods
6. **For `non-root` failures:** Add `securityContext.runAsNonRoot: true` to the container or pod spec
7. **For `host-users` failures:** Add `spec.hostUsers: false` to the PodSpec (or `spec.template.spec.hostUsers: false` for Deployments/StatefulSets/DaemonSets/Jobs/CronJobs). Requires Kubernetes ≥1.36 in the target cluster. Privileged workloads that must share the host user namespace (e.g. log shippers reading host paths, kubelets, container-runtime sidecars) can use `include`/`exclude` in `lunar-config.yml` to opt out.
8. **For `host-network` failures:** Remove `spec.hostNetwork: true` from the PodSpec. Workloads that legitimately need the host network (CNI agents, node-local proxies, host-bound metrics exporters) can opt out via `include`/`exclude` in `lunar-config.yml`.
9. **For `host-pid` failures:** Remove `spec.hostPID: true` from the PodSpec. Node-level monitoring agents that need a host-wide process view can opt out via `include`/`exclude` in `lunar-config.yml`.
10. **For `host-ipc` failures:** Remove `spec.hostIPC: true` from the PodSpec. Workloads that genuinely need host IPC (rare — usually legacy shared-memory consumers) can opt out via `include`/`exclude` in `lunar-config.yml`.
11. **For `metadata-egress-blocked` failures:** Select the workload with a NetworkPolicy that has `Egress` in `policyTypes`, namespace-wide (`podSelector: {}`) or per workload, and allow `0.0.0.0/0` with `except: [169.254.169.254/32]`, or no egress at all. Policies are additive: any selecting policy with a rule that has no `to`, or an `ipBlock` without the `except`, reopens TCP 80 to the endpoint. Only `networking.k8s.io` NetworkPolicy in this repository is read, so exclude the check where the endpoint is blocked some other way (e.g. AdminNetworkPolicy), or where pods need it by design (GKE Workload Identity serves them through it). `hostNetwork` workloads are left to `host-network`.
12. **For `min-kubectl-version` failures:** Upgrade the kubectl client in your CI pipeline (e.g., pin `azure/setup-kubectl@v4` or `setup-kubectl` action to a newer version, or update the installed kubectl on self-hosted runners)
13. **For `topology-spread` failures:** Add a `topologySpreadConstraints` entry with `topologyKey` set to `topology_key`, a `labelSelector` matching the pod template labels, and `maxSkew` within `topology_max_skew`
14. **For `graceful-shutdown` failures:** Add a `lifecycle.preStop` hook (for example `sleep: {seconds: 5}`) so endpoints are removed before the process gets SIGTERM, make the application drain on SIGTERM, and raise `terminationGracePeriodSeconds` to cover the preStop delay plus the longest request
15. **For `pdb-budget` failures:** Set `maxUnavailable` to 1 (or a percentage) instead of a `minAvailable` that equals the replica count, set only one of the two fields, and give the budget a `selector`
16. **For `no-static-replicas` failures:** Stop rendering `spec.replicas` when an autoscaler manages the workload (in a chart, wrap it in `{{- if not .Values.autoscaling.enabled }}`), and set the floor on the autoscaler's minimum instead
17. **For `probes-distinct` failures:** Give liveness and readiness their own endpoints: liveness should only report whether the process is stuck, readiness whether the pod can take traffic right now
18. **For `probe-timeouts` failures:** Set `timeoutSeconds` explicitly, at or above `min_probe_timeout_seconds` and below `periodSeconds`
19. **For `allowed-registries` failures:** Pull the image from an approved registry, mirroring it there first if needed
20. **For `deprecated-api-versions` failures:** Move the resource to its current apiVersion (`kubectl convert` or the Kubernetes deprecation guide lists the replacement); in a chart, also check templates that pick the apiVersion from `.Capabilities`
21. **For `pod-annotations` failures:** Add the missing annotation under `spec.template.metadata.annotations`, or remove the forbidden one

Consumers who want any of these surfaced without blocking can pin `enforcement: report-pr` at config time — but that's a consumer-side knob; the checks themselves just pass or fail.
