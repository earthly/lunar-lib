# Terraform Guardrails

Enforces Terraform-specific configuration best practices.

## Overview

This policy enforces Terraform-specific standards that don't transfer to other IaC frameworks: provider version pinning, module version pinning, and remote backend usage. It also bundles a set of AWS resource security checks relevant to SOC 2 — such as encryption at rest, logging, public-access blocking, and network ingress limits — each individually includable. All checks read from `.iac.native.terraform.files[]` and analyze the parsed HCL. For generic IaC checks (validity, WAF, datastores), see the `iac` policy.

## Policies

This policy provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `provider-versions-pinned` | Providers specify version constraints | Provider in `required_providers` has no `version` field |
| `module-versions-pinned` | Modules use pinned versions | Module missing `version` or `?ref=` in source |
| `remote-backend` | Remote backend configured | No `terraform { backend {} }` block found |
| `min-provider-versions` | Providers meet minimum version requirements | Provider version constraint below required minimum |

The checks below are AWS resource security guardrails. Each maps to a SOC 2 / Secureframe control and is individually includable — a future SOC 2 starter-pack can bundle them all:

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `alb-waf-enabled` | Public ALBs have a WAF web ACL associated (SOC 2) | Internet-facing `aws_lb` with no `aws_wafv2_web_acl_association` |
| `cloudtrail-multi-region` | CloudTrail is multi-region and ships to CloudWatch (SOC 2) | No multi-region `aws_cloudtrail`, or no CloudWatch Logs group |
| `security-group-no-public-postgres` | No public ingress to PostgreSQL (SOC 2) | A security group allows `0.0.0.0/0` to port 5432 |
| `security-group-no-public-ssh` | No public ingress to SSH (SOC 2) | A security group allows `0.0.0.0/0` to port 22 |
| `eks-control-plane-logging` | EKS control-plane logging enabled (SOC 2) | `aws_eks_cluster` missing required `enabled_cluster_log_types` |
| `elb-access-logging` | Load balancers log access requests (SOC 2) | `aws_lb` / `aws_elb` without access logging enabled |
| `ebs-snapshot-encryption` | EBS snapshots encrypted at rest (SOC 2) | `aws_ebs_snapshot` without `encrypted = true` |
| `ebs-volume-encryption` | EBS volumes encrypted at rest (SOC 2) | `aws_ebs_volume` or block device without `encrypted = true` |
| `elb-https-only` | Load balancers enforce HTTPS/TLS (SOC 2) | Plaintext HTTP listener without an HTTPS redirect |
| `guardduty-enabled` | GuardDuty detector enabled (SOC 2) | No `aws_guardduty_detector` with `enable = true` |
| `rds-cloudwatch-logging` | RDS exports logs to CloudWatch (SOC 2) | RDS instance/cluster without `enabled_cloudwatch_logs_exports` |
| `s3-block-public-access` | S3 buckets block public access (SOC 2) | Bucket without a full `aws_s3_bucket_public_access_block` |
| `s3-access-logging` | S3 buckets log access requests (SOC 2) | Bucket without server access logging configured |
| `vpc-flow-logs` | VPCs have flow logs enabled (SOC 2) | `aws_vpc` without a matching `aws_flow_log` |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.iac.native.terraform.files[]` | array | `terraform` collector |

**Note:** Ensure the `terraform` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/terraform@main
    on: [infra]

policies:
  - uses: github://earthly/lunar-lib/policies/terraform@main
    on: [infra]
    enforcement: report-pr
    # include: [provider-versions-pinned, remote-backend]  # Only run specific checks
    # with:
    #   required_backend_types: "s3,gcs,remote"  # Restrict allowed backend types
    #   min_provider_versions: '{"aws": "5.0", "random": "3.0"}'  # Enforce minimum versions
```

## Examples

### Passing Example

A component with pinned providers, versioned modules, and a remote backend:

```json
{
  "iac": {
    "native": {
      "terraform": {
        "files": [
          {
            "path": "main.tf",
            "hcl": {
              "terraform": [
                {
                  "required_providers": [
                    {
                      "aws": {"source": "hashicorp/aws", "version": "~> 5.0"},
                      "random": {"source": "hashicorp/random", "version": ">= 3.0"}
                    }
                  ],
                  "backend": [
                    {"s3": {"bucket": "my-state", "key": "state.tfstate"}}
                  ]
                }
              ],
              "module": {
                "vpc": [{"source": "terraform-aws-modules/vpc/aws", "version": "5.1.0"}]
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

A component with unpinned providers, unversioned modules, and no backend:

```json
{
  "iac": {
    "native": {
      "terraform": {
        "files": [
          {
            "path": "main.tf",
            "hcl": {
              "terraform": [
                {
                  "required_providers": [
                    {
                      "aws": {"source": "hashicorp/aws"},
                      "random": {"source": "hashicorp/random"}
                    }
                  ]
                }
              ],
              "module": {
                "vpc": [{"source": "terraform-aws-modules/vpc/aws"}],
                "rds": [{"source": "git::https://github.com/org/tf-module.git"}]
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
- `Providers without version constraints: aws, random. Add version constraints in required_providers to ensure reproducible deployments.`
- `Modules without pinned versions: vpc, rds. Add version constraints or use ?ref= to pin module sources.`
- `No backend configured. Terraform state is stored locally, which is fragile and cannot be shared across teams.`

## Remediation

When this policy fails, resolve it by:

1. **For `provider-versions-pinned` failures:** Add `version` constraints to each provider in `required_providers`:
   ```hcl
   terraform {
     required_providers {
       aws = {
         source  = "hashicorp/aws"
         version = "~> 5.0"
       }
     }
   }
   ```
2. **For `module-versions-pinned` failures:** Add `version` to registry modules or `?ref=` to git sources:
   ```hcl
   module "vpc" {
     source  = "terraform-aws-modules/vpc/aws"
     version = "5.1.0"
   }
   ```
3. **For `remote-backend` failures:** Configure a remote backend for shared state:
   ```hcl
   terraform {
     backend "s3" {
       bucket = "my-terraform-state"
       key    = "state.tfstate"
       region = "us-east-1"
     }
   }
   ```
