# Category: `.iac`

Infrastructure as Code. Normalized across Terraform, Pulumi, CloudFormation, etc.

```json
{
  "iac": {
    "source": {"tool": "hcl2json", "version": "0.6.8"},
    "files": [
      {"path": "infra/main.tf", "valid": true}
    ],
    "modules": [
      {
        "path": "infra",
        "resources": [
          {"type": "aws_db_instance", "name": "main", "category": "datastore", "has_prevent_destroy": true},
          {"type": "aws_lb", "name": "api", "category": "network", "has_prevent_destroy": false, "internet_facing": true},
          {"type": "aws_wafv2_web_acl", "name": "main", "category": "security"}
        ],
        "analysis": {
          "internet_accessible": true,
          "has_waf": true
        }
      }
    ],
    "native": {
      "terraform": {
        "files": [
          {"path": "infra/main.tf", "hcl": {}}
        ]
      }
    }
  }
}
```

## Key Policy Paths

- `.iac.files[].valid` — Config files valid
- `.iac.modules[].path` — Module directory path
- `.iac.modules[].resources[]` — Normalized resources with `type`, `name`, `category`, `has_prevent_destroy`
- `.iac.modules[].analysis.internet_accessible` — Module has public resources
- `.iac.modules[].analysis.has_waf` — Module has WAF protection
- `.iac.native.terraform.files[].hcl` — Full parsed HCL (for terraform-specific policy)
