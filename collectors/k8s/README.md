# Kubernetes Collector

Parses Kubernetes manifests, renders Helm charts, and tracks kubectl commands in CI.

## Overview

This collector finds all Kubernetes YAML manifests in a repository and validates them using [kubeconform](https://github.com/yannh/kubeconform). It renders each Helm chart with `helm template` and parses the output the same way, so workloads defined in charts are checked like plain manifests. It extracts workloads (Deployments, StatefulSets, DaemonSets, Jobs, CronJobs) with their container specs, resource limits, probes and shutdown settings, plus PodDisruptionBudgets, HorizontalPodAutoscalers, KEDA ScaledObjects and NetworkPolicies. It also intercepts `kubectl` commands during CI runs so deployment invocations (apply, rollout, etc.) are recorded alongside the manifest data.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.k8s.source` | object | Tool metadata (tool name and version) |
| `.k8s.manifests[]` | array | Parsed manifests with validity and resources: one entry per static file, and one per chart render |
| `.k8s.workloads[]` | array | Workload resources with `pod_labels`, `pod_annotations`, replica, scheduling and shutdown settings, and `containers[]` / `init_containers[]` (resources, probes, security context) |
| `.k8s.pdbs[]` | array | PodDisruptionBudgets with their full label `selector` (`target_workload` is deprecated) |
| `.k8s.hpas[]` | array | HorizontalPodAutoscalers |
| `.k8s.scaled_objects[]` | array | KEDA ScaledObjects, with the workload they scale and their replica range |
| `.k8s.network_policies[]` | array | NetworkPolicies: `pod_selector`, effective `policy_types` (API-server default when unset), and `egress` rules as written |
| `.k8s.cicd` | object | kubectl CI command tracking (commands + client version) |

Entries that come from a Helm chart carry `render`: the chart directory and the values files it was rendered with. Their `path` is the chart template that produced them, such as `charts/api/templates/deployment.yaml`; for a packaged dependency it names the template inside the package.

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `k8s` | Parses Kubernetes manifests, workloads, PodDisruptionBudgets, autoscalers, and NetworkPolicies |
| `helm` | Renders Helm charts and parses the output into the same paths |
| `cicd` | Tracks all kubectl commands executed in CI pipelines (apply, rollout, etc.) |

### Helm charts

The `helm` collector renders each chart it finds (a directory with a `Chart.yaml`) with `helm template`, offline. Library charts aren't rendered, and a subchart in another chart's `charts/` directory is rendered as part of its parent. The `k8s` collector still skips templated files, so a chart's templates are only ever read through its render.

By default each chart renders once, with its own `values.yaml`. To check the values a chart is deployed with, list them in `helm_values`, one render per line:

```yaml
helm_values: |
  values-staging.yaml
  values-prod.yaml values-prod-eu.yaml   # files apply in order, on top of values.yaml
  ci/*-values.yaml                       # a glob gives one render per matching file
```

Paths are relative to the chart directory, and every line applies to every chart. A chart skips the lines whose files it doesn't have, and renders with `values.yaml` alone when none apply.

Charts render against helm's built-in Kubernetes version and core APIs. A chart that only renders an object when its CRD is installed, such as a KEDA ScaledObject behind `.Capabilities.APIVersions.Has "keda.sh/v1alpha1"`, needs that API listed in `helm_api_versions`.

The values sets of one chart are alternative deployments of the same release, so policies never match a workload to a PodDisruptionBudget, autoscaler or NetworkPolicy from another values set of its own chart. Objects from plain manifests and from other charts still match.

A chart that fails to render gets a `.k8s.manifests[]` entry with `valid: false` and helm's error, so the `valid` check fails instead of every check skipping. Remote dependencies must be vendored in the chart's `charts/` directory, or set `helm_dependency_build: true` to fetch them first, which needs network access to the chart repositories. Local `file://` dependencies are built either way.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/k8s@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [kubernetes, backend]
    # exclude: [helm]  # Don't render Helm charts
    # with:
    #   find_command: "find ./deploy -name '*.yaml'"  # Custom find command
    #   helm_values: |
    #     values-prod.yaml
    #   helm_dependency_build: "true"  # Fetch remote chart dependencies (needs network)
    #   helm_api_versions: "keda.sh/v1alpha1"  # Render objects gated on a CRD
```
