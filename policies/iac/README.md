# IaC Guardrails

Enforces Infrastructure as Code configuration best practices.

## Overview

This policy validates IaC configurations against best practices including file validity, WAF protection for internet-facing services, and destroy protection for both stateful (datastores) and stateless (compute, networking) resources. It analyzes parsed IaC data from the `.iac` category and works across IaC frameworks (Terraform, Pulumi, CloudFormation).

## Policies

This policy provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `valid` | All IaC files parse successfully | File has syntax errors |
| `waf-protection` | Internet-facing services have WAF | Public service without WAF protection |
| `datastore-destroy-protection` | Stateful resources have destroy protection | Datastore missing `lifecycle { prevent_destroy = true }` |
| `resource-destroy-protection` | Stateless resources have destroy protection | Infrastructure resource missing `lifecycle { prevent_destroy = true }` |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.iac.files[]` | array | `terraform` collector |
| `.iac.native.terraform.files[]` | array | `terraform` collector |

**Note:** Ensure the `terraform` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/terraform@main
    on: [infra]

policies:
  - uses: github://earthly/lunar-lib/policies/iac@main
    on: [infra]
    enforcement: report-pr
    # include: [valid, waf-protection, datastore-destroy-protection]  # Only run specific checks
    # with:
    #   extra_datastore_types: "aws_redshift_cluster,aws_neptune_cluster"
    #   extra_stateless_types: "aws_ecs_cluster,aws_eks_cluster"
```

## Examples

### Passing Example

A component with valid Terraform, WAF-protected internet services, and protected resources:

```json
{
  "iac": {
    "files": [
      {"path": "main.tf", "valid": true},
      {"path": "network.tf", "valid": true}
    ],
    "native": {
      "terraform": {
        "files": [
          {
            "path": "main.tf",
            "hcl": {
              "resource": {
                "aws_db_instance": {
                  "main": [{"lifecycle": [{"prevent_destroy": true}]}]
                },
                "aws_lb": {
                  "api": [{"internal": false, "lifecycle": [{"prevent_destroy": true}]}]
                },
                "aws_wafv2_web_acl": {"main": [{}]},
                "aws_wafv2_web_acl_association": {"api": [{}]}
              }
            }
          }
        ]
      }
    }
  }
}
```

### Failing Example

A component with an internet-facing load balancer but no WAF, and unprotected resources:

```json
{
  "iac": {
    "files": [
      {"path": "main.tf", "valid": true}
    ],
    "native": {
      "terraform": {
        "files": [
          {
            "path": "main.tf",
            "hcl": {
              "resource": {
                "aws_db_instance": {
                  "payments_db": [{"engine": "postgres"}]
                },
                "aws_instance": {
                  "web": [{"instance_type": "t3.micro"}]
                },
                "aws_lb": {
                  "api": [{"internal": false}]
                }
              }
            }
          }
        ]
      }
    }
  }
}
```

**Failure messages:**
- `Service has internet-facing resources but no WAF protection configured`
- `Stateful resources without destroy protection: aws_db_instance.payments_db`
- `Stateless resources without destroy protection: aws_instance.web, aws_lb.api`

## Remediation

When this policy fails, resolve it by:

1. **For `valid` failures:** Fix HCL syntax errors in the flagged `.tf` files
2. **For `waf-protection` failures:** Add `aws_wafv2_web_acl` and `aws_wafv2_web_acl_association` resources to protect internet-facing load balancers and API gateways
3. **For `datastore-destroy-protection` failures:** Add `lifecycle { prevent_destroy = true }` to database, storage, and cache resources
4. **For `resource-destroy-protection` failures:** Add `lifecycle { prevent_destroy = true }` to critical infrastructure resources like EC2 instances, load balancers, and networking components
