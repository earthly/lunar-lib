# Category: `.iac`

Infrastructure as Code. Normalized across Terraform, Pulumi, CloudFormation, etc.

```json
{
  "iac": {
    "tool": "terraform",
    "files": [
      {
        "path": "infrastructure/main.tf",
        "valid": true
      }
    ],
    "resources": [
      {
        "type": "database",
        "provider": "aws",
        "resource_type": "aws_db_instance",
        "name": "payments_db",
        "path": "infrastructure/database.tf",
        "deletion_protected": true,
        "encrypted": true,
        "backup_enabled": true,
        "multi_az": true
      },
      {
        "type": "storage",
        "provider": "aws",
        "resource_type": "aws_s3_bucket",
        "name": "payment_logs",
        "path": "infrastructure/storage.tf",
        "deletion_protected": true,
        "versioning_enabled": true,
        "encrypted": true
      },
      {
        "type": "load_balancer",
        "provider": "aws",
        "resource_type": "aws_alb",
        "name": "api_lb",
        "path": "infrastructure/network.tf",
        "internet_facing": true,
        "waf_enabled": true,
        "ssl_policy": "ELBSecurityPolicy-TLS-1-2-2017-01"
      }
    ],
    "analysis": {
      "has_backend": true,
      "versions_pinned": true,
      "internet_accessible": true,
      "has_waf": true
    },
    "datastores": {
      "count": 2,
      "all_deletion_protected": true,
      "all_encrypted": true,
      "unprotected": []
    },
    "summary": {
      "all_valid": true,
      "resource_count": 15
    }
  }
}
```

## Key Policy Paths

- `.iac.files[].valid` — Config files valid
- `.iac.analysis.internet_accessible` — Public resources
- `.iac.analysis.has_waf` — WAF configured
- `.iac.datastores.all_deletion_protected` — Delete protection
- `.iac.datastores.all_encrypted` — Encryption at rest
- `.iac.resources[].type` — Normalized resource type for queries
