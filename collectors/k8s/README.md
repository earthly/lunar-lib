# Kubernetes Collector

Parses Kubernetes manifests and collects workload, PodDisruptionBudget, and HorizontalPodAutoscaler metadata.

## Overview

This collector finds all Kubernetes YAML manifests in a repository and validates them using [kubeconform](https://github.com/yannh/kubeconform). It extracts structured information about workloads (Deployments, StatefulSets, DaemonSets, Jobs, CronJobs), their container specifications including resource limits and probes, PodDisruptionBudgets, and HorizontalPodAutoscalers. The collector runs on code changes and outputs normalized data for K8s-related policies.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.k8s.source` | object | Tool metadata (tool name and version) |
| `.k8s.manifests[]` | array | Parsed K8s manifests with validity and resources |
| `.k8s.workloads[]` | array | Workload resources with container specs |
| `.k8s.pdbs[]` | array | PodDisruptionBudgets |
| `.k8s.hpas[]` | array | HorizontalPodAutoscalers |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `k8s` | Collects Kubernetes manifests, workloads, PodDisruptionBudgets, and HorizontalPodAutoscalers |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/k8s@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [kubernetes, backend]
    # with:
    #   find_command: "find ./deploy -name '*.yaml'"  # Custom find command
```

