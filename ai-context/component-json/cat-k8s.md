# Category: `.k8s`

Kubernetes manifests. This is specific enough to warrant its own category.

Plain manifests and rendered Helm charts share the same arrays. An entry that came from a chart carries `render` (the chart directory and the values files it was rendered with), and its `path` is the template that produced it. A chart no `helm_values` line applies to is rendered with its defaults only to check that it builds: its `.k8s.manifests[]` entry has `render.validated_only: true`, and it contributes no other entries.

```json
{
  "k8s": {
    "manifests": [
      {
        "path": "deploy/deployment.yaml",
        "valid": true,
        "error": null,
        "resources": [
          {
            "kind": "Deployment",
            "name": "payment-api",
            "namespace": "payments",
            "api_version": "apps/v1"
          }
        ]
      },
      {
        "path": "charts/worker",
        "render": {"chart": "charts/worker", "values": ["values.yaml", "values-prod.yaml"], "validated_only": false},
        "valid": true,
        "resources": [
          {"kind": "Deployment", "name": "worker", "namespace": "default", "api_version": "apps/v1"}
        ]
      }
    ],
    "workloads": [
      {
        "kind": "Deployment",
        "name": "payment-api",
        "namespace": "payments",
        "path": "deploy/deployment.yaml",
        "replicas": 3,
        "replicas_set": true,
        "pod_labels": {"app": "payment-api", "tier": "api"},
        "pod_annotations": {"prometheus.io/scrape": "true"},
        "termination_grace_period_seconds": 60,
        "topology_spread_constraints": [
          {
            "topology_key": "topology.kubernetes.io/zone",
            "max_skew": 1,
            "when_unsatisfiable": "ScheduleAnyway",
            "label_selector": {"matchLabels": {"app": "payment-api"}},
            "match_label_keys": ["pod-template-hash"]
          }
        ],
        "containers": [
          {
            "name": "api",
            "image": "gcr.io/acme/payment-api:v1.2.3",
            "has_resources": true,
            "has_requests": true,
            "has_limits": true,
            "cpu_request": "100m",
            "cpu_limit": "500m",
            "memory_request": "128Mi",
            "memory_limit": "512Mi",
            "has_liveness_probe": true,
            "has_readiness_probe": true,
            "liveness_probe": {"handler": "httpGet", "port": 8080, "path": "/livez", "initial_delay_seconds": 0, "period_seconds": 10, "timeout_seconds": 2, "failure_threshold": 3},
            "readiness_probe": {"handler": "httpGet", "port": 8080, "path": "/readyz", "initial_delay_seconds": 0, "period_seconds": 5, "timeout_seconds": 2, "failure_threshold": 3},
            "startup_probe": null,
            "has_prestop": true,
            "runs_as_non_root": true,
            "read_only_root_fs": true,
            "privileged": false
          }
        ],
        "init_containers": []
      }
    ],
    "pdbs": [
      {
        "name": "payment-api-pdb",
        "namespace": "payments",
        "path": "deploy/pdb.yaml",
        "selector": {"matchLabels": {"app": "payment-api"}},
        "target_workload": "payment-api",
        "min_available": 2
      }
    ],
    "hpas": [
      {
        "name": "payment-api-hpa",
        "namespace": "payments",
        "path": "deploy/hpa.yaml",
        "target_workload": "payment-api",
        "min_replicas": 3,
        "max_replicas": 10
      }
    ],
    "scaled_objects": [
      {
        "name": "worker",
        "namespace": "default",
        "path": "charts/worker/templates/scaledobject.yaml",
        "render": {"chart": "charts/worker", "values": ["values.yaml", "values-prod.yaml"]},
        "target_workload": "worker",
        "min_replicas": 2,
        "max_replicas": 20
      }
    ],
    "network_policies": [
      {
        "name": "egress-no-metadata",
        "namespace": "payments",
        "path": "deploy/netpol.yaml",
        "pod_selector": {},
        "policy_types": ["Egress"],
        "egress": [
          {"to": [{"ipBlock": {"cidr": "0.0.0.0/0", "except": ["169.254.169.254/32"]}}]}
        ]
      }
    ],
    "summary": {
      "all_valid": true,
      "all_have_resources": true,
      "all_have_probes": true,
      "all_non_root": true,
      "all_have_pdb": true
    }
  }
}
```

Effective values are recorded: an unset `replicas` is 1, an unset `termination_grace_period_seconds` is 30, and an unset probe timing takes the Kubernetes default. `replicas_set` says whether the manifest sets `spec.replicas` itself.

## Key Policy Paths

- `.k8s.manifests[].valid` — Manifest parses (for a chart render, `false` also means the chart failed to render)
- `.k8s.manifests[].resources[].api_version` — Deprecated API detection
- `.k8s.workloads[].containers[].has_resources` — Resource limits set
- `.k8s.workloads[].containers[].runs_as_non_root` — Security context
- `.k8s.workloads[].containers[].liveness_probe` / `readiness_probe` — Probe endpoints and timing
- `.k8s.workloads[].topology_spread_constraints` — Zone spread
- `.k8s.hpas[].min_replicas` — HPA minimum
- `.k8s.summary.all_have_pdb` — All workloads have PDB
- `.k8s.pdbs[].selector` vs `.k8s.workloads[].pod_labels` — PDB coverage. Match with LabelSelector semantics; `pdbs[].target_workload` is a deprecated name guess
- `.k8s.network_policies[]` — `pod_selector` and `egress` as written; `policy_types` is effective (the API server's default when unset). Egress isolation per workload = a policy in its namespace whose `pod_selector` matches its `pod_labels` with `Egress` in `policy_types`
- `render` — Never match a workload to a PDB, autoscaler or NetworkPolicy from another values set of its own chart; plain manifests and other charts match as usual
- `.k8s.hpas[]` / `.k8s.scaled_objects[]` vs `.k8s.workloads[].replicas` — An autoscaler targeting a workload sets its size range (min for disruption budgets, max for spread); `replicas` applies only without one
