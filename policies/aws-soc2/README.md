# AWS SOC 2 Guardrails

Enforce SOC 2 AWS infrastructure controls against your Terraform — encryption, logging, network exposure, and threat detection.

## Overview

This policy bundle codifies a set of SOC 2 / Secureframe AWS infrastructure
controls as Terraform guardrails. Each check reads the parsed Terraform HCL
produced by the `terraform` collector and verifies that AWS resources are
configured to satisfy a specific control — for example, that EBS volumes are
encrypted, S3 buckets block public access, and CloudTrail is multi-region.
Use it to catch compliance drift in pull requests before infrastructure ever
reaches production.

## Policies

This plugin provides the following policies (use `include` to select a subset).
Each maps to a SOC 2 control tracked in Secureframe:

| Policy | SOC 2 / Secureframe Control | Description |
|--------|-----------------------------|-------------|
| `alb-waf-enabled` | Application load balancer WAF (AWS) | Public ALBs must have a WAF web ACL associated |
| `cloudtrail-multi-region` | CloudTrail multi-region configuration (AWS) | CloudTrail must be multi-region and ship to CloudWatch Logs |
| `security-group-no-public-postgres` | EC2 security group port restriction (PostgreSQL) (AWS) | No unrestricted ingress to the PostgreSQL port |
| `security-group-no-public-ssh` | EC2 security group port restriction (SSH) (AWS) | No unrestricted ingress to the SSH port |
| `eks-control-plane-logging` | EKS logging integration with CloudWatch (AWS) | EKS control-plane logging must be enabled |
| `elb-access-logging` | ELB logging (AWS) | Load balancers must have access logging enabled |
| `ebs-snapshot-encryption` | Elastic Block Store snapshot encryption at rest (AWS) | EBS snapshots must be encrypted |
| `ebs-volume-encryption` | Elastic Block Store volume encryption at rest (AWS) | EBS volumes must be encrypted |
| `elb-https-only` | Elastic Load Balancer encryption in transit (AWS) | Load balancers must enforce HTTPS/TLS |
| `guardduty-enabled` | GuardDuty enabled (AWS) | GuardDuty detector must be enabled |
| `rds-cloudwatch-logging` | RDS logging integration with CloudWatch (AWS) | RDS must export logs to CloudWatch |
| `s3-block-public-access` | S3 bucket public access restriction (AWS) | S3 buckets must block public access |
| `s3-access-logging` | S3 bucket server access logging (AWS) | S3 buckets must have server access logging |
| `vpc-flow-logs` | VPC flow logs enabled (AWS) | VPCs must have flow logs enabled |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.iac.native.terraform.files` | array | `terraform` collector |
| `.iac.native.terraform.files[].hcl` | object | `terraform` collector |

**Note:** Enable the [`terraform`](../../collectors/terraform) collector before
using this policy — it parses `.tf` files into the HCL JSON these checks read.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/aws-soc2@v1.0.0
    on: [terraform]            # Or your IaC tag / domain selector
    enforcement: report-pr     # draft, score, report-pr, block-pr, block-release, block-pr-and-release
    # include:                 # Omit to run all 14 checks
    #   - ebs-volume-encryption
    #   - s3-block-public-access
    # with:                    # Override defaults if needed
    #   ssh_port: "22"
    #   postgres_port: "5432"
```

## Examples

A check resolves to **skip** when the relevant resource type is absent (e.g.
`ebs-volume-encryption` skips a component with no EBS volumes), **pass** when
every matching resource is compliant, and **fail** when a resource is present
but misconfigured.

### Passing Example

An EBS volume with encryption enabled:

```json
{
  "iac": {
    "native": {
      "terraform": {
        "files": [
          {
            "path": "deploy/main.tf",
            "hcl": {
              "resource": {
                "aws_ebs_volume": {
                  "data": [{"availability_zone": "us-east-1a", "size": 100, "encrypted": true}]
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

### Failing Example

The same volume with encryption omitted (defaults to unencrypted):

```json
{
  "iac": {
    "native": {
      "terraform": {
        "files": [
          {
            "path": "deploy/main.tf",
            "hcl": {
              "resource": {
                "aws_ebs_volume": {
                  "data": [{"availability_zone": "us-east-1a", "size": 100}]
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

**Failure message:** `aws_ebs_volume.data is not encrypted at rest (set encrypted = true)`

## Remediation

When a check fails, update the offending Terraform resource to satisfy the
control, then re-run the plan:

1. Read the failure message — it names the resource (`type.name`) and the
   missing attribute or associated resource.
2. Add the required configuration. Common fixes:
   - `encrypted = true` on `aws_ebs_volume` / `aws_ebs_snapshot`.
   - An `aws_s3_bucket_public_access_block` (all four flags `true`) per bucket.
   - An `aws_flow_log` referencing each `aws_vpc`.
   - `is_multi_region_trail = true` plus `cloud_watch_logs_group_arn` on
     `aws_cloudtrail`.
   - Remove `0.0.0.0/0` / `::/0` ingress on SSH (22) and PostgreSQL (5432).
3. For account-wide controls (`cloudtrail-multi-region`, `guardduty-enabled`),
   apply the check only to the component that owns the account baseline using
   `on:` selectors or `include`.
