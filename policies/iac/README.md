# IaC Guardrails

Enforces Infrastructure as Code configuration best practices.

## Overview

This policy validates IaC configurations against best practices including file validity, WAF protection for internet-facing services, datastore durability, and infrastructure availability. It analyzes parsed IaC data from the `.iac` category and works across IaC frameworks (Terraform, Pulumi, CloudFormation).

## Policies

This policy provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `valid` | All IaC files parse successfully | File has syntax errors |
| `waf-protection` | Internet-facing services have WAF | Public service without WAF protection |
| `datastore-durability` | Datastores have deletion protection | Datastore missing `lifecycle { prevent_destroy = true }` |
| `infra-availability` | Infrastructure has availability best practices | Missing multi-AZ or auto-scaling configuration |

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
    # include: [valid, waf-protection, datastore-durability]  # Only run specific checks
    # with:
    #   extra_datastore_types: "aws_redshift_cluster,aws_neptune_cluster"  # Add custom types
```

## Examples

### Passing Example

A component with valid Terraform, WAF-protected internet services, and protected datastores:

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
                  "api": [{"internal": false}]
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

A component with an internet-facing load balancer but no WAF, and unprotected datastores:

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
- `Datastores without deletion protection: aws_db_instance.payments_db. Add lifecycle { prevent_destroy = true } to protect against accidental deletion.`
- `Infrastructure resource aws_db_instance.main is not configured for multi-AZ deployment`

## Remediation

When this policy fails, resolve it by:

1. **For `valid` failures:** Fix HCL syntax errors in the flagged `.tf` files
2. **For `waf-protection` failures:** Add `aws_wafv2_web_acl` and `aws_wafv2_web_acl_association` resources to protect internet-facing load balancers and API gateways
3. **For `datastore-durability` failures:** Add `lifecycle { prevent_destroy = true }` to database, storage, and cache resources to prevent accidental deletion
4. **For `infra-availability` failures:** Enable multi-AZ deployment, configure auto-scaling groups, or add redundancy for critical infrastructure resources
