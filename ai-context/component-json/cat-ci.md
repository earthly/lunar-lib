# Category: `.ci`

CI/CD pipeline data.

```json
{
  "ci": {
    "platform": "github-actions",
    "run": {
      "id": "12345",
      "status": "success",
      "duration_seconds": 342
    },
    "jobs": [
      {"name": "build", "status": "success", "duration_seconds": 120},
      {"name": "test", "status": "success", "duration_seconds": 180}
    ],
    "steps_executed": {
      "lint": true,
      "build": true,
      "unit_test": true,
      "integration_test": true,
      "security_scan": true,
      "deploy": false
    },
    "artifacts": {
      "images_pushed": ["gcr.io/acme/payment-api:v1.2.3"],
      "packages_published": [],
      "sbom_generated": true
    },
    "performance": {
      "avg_duration_seconds": 350
    }
  }
}
```

## Key Policy Paths

- `.ci.run.status` — Current run status
- `.ci.steps_executed.<step>` — Specific step ran
- `.ci.artifacts.sbom_generated` — SBOM created
- `.ci.performance.avg_duration_seconds` — CI speed
