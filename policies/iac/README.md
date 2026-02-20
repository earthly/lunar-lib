# IaC Guardrails

Enforces Infrastructure as Code configuration best practices.

## Overview

This policy validates IaC configurations against best practices including file validity, WAF protection for internet-facing services, and destroy protection for both stateful (datastores) and stateless (compute, networking) resources. It reads normalized data from `.iac.modules[]` and works across IaC frameworks (Terraform, Pulumi, CloudFormation).

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
| `.iac.modules[]` | array | `terraform` collector |
| `.iac.modules[].resources[]` | array | `terraform` collector |
| `.iac.modules[].analysis` | object | `terraform` collector |

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
```

## Examples

### Passing Example

A component with valid Terraform, WAF-protected internet services, and protected datastores:

```json
{
  "iac": {
    "files": [{"path": "main.tf", "valid": true}],
    "modules": [
      {
        "path": "deploy/terraform",
        "resources": [
          {"type": "aws_db_instance", "name": "main", "category": "datastore", "has_prevent_destroy": true},
          {"type": "aws_lb", "name": "api", "category": "network", "has_prevent_destroy": true, "internet_facing": true},
          {"type": "aws_wafv2_web_acl", "name": "main", "category": "security"},
          {"type": "aws_wafv2_web_acl_association", "name": "api", "category": "security"}
        ],
        "analysis": {"internet_accessible": true, "has_waf": true}
      }
    ]
  }
}
```

### Failing Example

A component with an internet-facing load balancer but no WAF, and unprotected datastores:

```json
{
  "iac": {
    "files": [{"path": "main.tf", "valid": true}],
    "modules": [
      {
        "path": "deploy/terraform",
        "resources": [
          {"type": "aws_db_instance", "name": "payments_db", "category": "datastore", "has_prevent_destroy": false},
          {"type": "aws_instance", "name": "web", "category": "compute", "has_prevent_destroy": false},
          {"type": "aws_lb", "name": "api", "category": "network", "has_prevent_destroy": false, "internet_facing": true}
        ],
        "analysis": {"internet_accessible": true, "has_waf": false}
      }
    ]
  }
}
```

**Failure messages:**
- `Module 'deploy/terraform': internet-facing resources without WAF protection`
- `Module 'deploy/terraform': stateful resources without destroy protection: aws_db_instance.payments_db`
- `Module 'deploy/terraform': stateless resources without destroy protection: aws_instance.web, aws_lb.api`

## Remediation

When this policy fails, resolve it by:

1. **For `valid` failures:** Fix HCL syntax errors in the flagged `.tf` files
2. **For `waf-protection` failures:** Add `aws_wafv2_web_acl` and `aws_wafv2_web_acl_association` resources to protect internet-facing load balancers and API gateways
3. **For `datastore-destroy-protection` failures:** Add `lifecycle { prevent_destroy = true }` to database, storage, and cache resources
4. **For `resource-destroy-protection` failures:** Add `lifecycle { prevent_destroy = true }` to critical infrastructure resources like EC2 instances, load balancers, and networking components
