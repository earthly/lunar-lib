# Category: `.k8s`

Kubernetes manifests. This is specific enough to warrant its own category.

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
            "namespace": "payments"
          }
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
            "runs_as_non_root": true,
            "read_only_root_fs": true,
            "privileged": false
          }
        ]
      }
    ],
    "pdbs": [
      {
        "name": "payment-api-pdb",
        "namespace": "payments",
        "path": "deploy/pdb.yaml",
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

## Key Policy Paths

- `.k8s.manifests[].valid` — Manifest parses
- `.k8s.workloads[].containers[].has_resources` — Resource limits set
- `.k8s.workloads[].containers[].runs_as_non_root` — Security context
- `.k8s.hpas[].min_replicas` — HPA minimum
- `.k8s.summary.all_have_pdb` — All workloads have PDB
