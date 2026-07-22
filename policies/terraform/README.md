# Terraform Guardrails

Enforces Terraform-specific configuration best practices.

## Overview

This policy enforces Terraform-specific standards that don't transfer to other IaC frameworks: provider version pinning, module version pinning, and remote backend usage. It also bundles a set of AWS resource security checks relevant to SOC 2 — such as encryption at rest, logging, public-access blocking, and network ingress limits — each individually includable, plus resource-tagging governance checks. Most checks read from `.iac.native.terraform.files[]` and analyze the parsed HCL; the tagging checks read the normalized `.iac.modules[]` view. For generic IaC checks (validity, WAF, datastores), see the `iac` policy.

## Policies

This policy provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `provider-versions-pinned` | Providers specify version constraints | Provider in `required_providers` has no `version` field |
| `module-versions-pinned` | Modules use pinned versions | Module missing `version` or `?ref=` in source |
| `remote-backend` | Remote backend configured | No `terraform { backend {} }` block found |
| `min-provider-versions` | Providers meet minimum version requirements | Provider version constraint below required minimum |

The checks below are AWS resource security guardrails relevant to SOC 2 (tagged with the `soc2` keyword). Each is individually includable — a future SOC 2 starter-pack can bundle them all:

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `aws-alb-waf-enabled` | Public ALBs have a WAF web ACL associated | Internet-facing `aws_lb` with no `aws_wafv2_web_acl_association` |
| `aws-cloudtrail-multi-region` | CloudTrail is multi-region and ships to CloudWatch | No multi-region `aws_cloudtrail`, or no CloudWatch Logs group |
| `aws-security-group-no-public-postgres` | No public ingress to PostgreSQL | A security group allows `0.0.0.0/0` to port 5432 |
| `aws-security-group-no-public-ssh` | No public ingress to SSH | A security group allows `0.0.0.0/0` to port 22 |
| `aws-eks-control-plane-logging` | EKS control-plane logging enabled | `aws_eks_cluster` missing required `enabled_cluster_log_types` |
| `aws-elb-access-logging` | Load balancers log access requests | `aws_lb` / `aws_elb` without access logging enabled |
| `aws-ebs-snapshot-encryption` | EBS snapshots encrypted at rest | `aws_ebs_snapshot` without `encrypted = true` |
| `aws-ebs-volume-encryption` | EBS volumes encrypted at rest | `aws_ebs_volume` or block device without `encrypted = true` |
| `aws-elb-https-only` | Load balancers enforce HTTPS/TLS | Plaintext HTTP listener without an HTTPS redirect |
| `aws-guardduty-enabled` | GuardDuty detector enabled | No `aws_guardduty_detector` with `enable = true` |
| `aws-rds-cloudwatch-logging` | RDS exports logs to CloudWatch | RDS instance/cluster without `enabled_cloudwatch_logs_exports` |
| `aws-s3-block-public-access` | S3 buckets block public access | Bucket without a full `aws_s3_bucket_public_access_block` |
| `aws-s3-access-logging` | S3 buckets log access requests | Bucket without server access logging configured |
| `aws-vpc-flow-logs` | VPCs have flow logs enabled | `aws_vpc` without a matching `aws_flow_log` |
| `aws-security-group-no-public-admin-ports` | No public ingress to sensitive admin/database ports | A security group allows `0.0.0.0/0` to a port like RDP, MySQL, MSSQL, or Telnet |
| `aws-rds-encryption-at-rest` | RDS storage is encrypted at rest | `aws_db_instance` / `aws_rds_cluster` without `storage_encrypted = true` |
| `aws-rds-not-publicly-accessible` | RDS is not publicly accessible | An RDS instance sets `publicly_accessible = true` |
| `aws-rds-snapshot-encryption` | RDS snapshots encrypted at rest | Snapshot whose source DB is not `storage_encrypted` |
| `aws-s3-encryption-at-rest` | S3 buckets declare encryption at rest | Bucket without a server-side encryption configuration |
| `aws-s3-no-static-website` | S3 buckets do not host static websites | Bucket with a website configuration (public hosting) |
| `aws-s3-no-public-acl` | S3 buckets do not grant public ACL access | Bucket with a `public-read`/`public-read-write` ACL or AllUsers grant |
| `aws-iam-password-min-length` | IAM password policy enforces a minimum length | No `aws_iam_account_password_policy`, or length below the minimum |
| `aws-iam-no-direct-user-policies` | No IAM policies attached directly to users | Inline/managed policy attached to a user instead of a group or role |
| `aws-acm-cert-dns-validation` | ACM certificates use DNS validation | `aws_acm_certificate` using EMAIL (or unset) validation |
| `aws-eks-private-endpoint` | EKS clusters enable private endpoint access | Cluster without `endpoint_private_access` / `cluster_endpoint_private_access` |
| `aws-dynamodb-encryption` | DynamoDB tables declare encryption at rest | Table without a `server_side_encryption { enabled = true }` block |
| `aws-lambda-not-public` | Lambda functions are not publicly invokable | `principal = "*"` permission without source scope, or function URL with `authorization_type = NONE` |
| `aws-cloudtrail-log-file-validation` | CloudTrail validates log-file integrity | Trail without `enable_log_file_validation = true` |
| `aws-cloudtrail-kms-encryption` | CloudTrail logs encrypted with KMS | Trail without `kms_key_id` |

The checks below govern **resource tagging**. They read the normalized `.iac.modules[]` view (not raw HCL) and are opt-in via inputs:

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `aws-resources-tagged` | Every taggable AWS resource carries the required tag key(s) | A non-exempt resource is missing a `required_tags` key (on neither its own `tags` nor the module's `default_tags`) |
| `entity-ref-valid` | The `entity_ref` tag value is a well-formed Backstage entity ref (and exists, when referential integrity is configured) | A resource's `entity_ref` tag value is malformed, the wrong kind, or resolved `exists: false` in Backstage |

### How the tagging checks handle unresolvable data

`hcl2json` never runs `terraform plan`, so the collector flags values it cannot resolve and these checks **skip rather than mis-verify** them:

- A resource whose `tags` attribute is an expression (`tags = merge(...)`, flagged `tags_expression`) is skipped by `aws-resources-tagged` (its keys can't be listed).
- A tag key present but with an interpolated value (`${var.x}`, listed in `tags_unresolved`) is treated as **present** by `aws-resources-tagged` (the key exists) but its value is **skipped** by `entity-ref-valid` (the value can't be verified).
- Provider-level `default_tags` (`.iac.modules[].default_tags`) count toward `aws-resources-tagged`, so a repo that tags everything via `default_tags` is not flagged.
- `entity-ref-valid` performs the existence check only when the `terraform` collector is configured with `backstage_url` (signalled by `.iac.refs.checked`); otherwise it does format validation only. A value the collector could not resolve due to a transient Backstage error is skipped, so an outage never turns the check red.

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.iac.native.terraform.files[]` | array | `terraform` collector (all checks except the tagging checks) |
| `.iac.modules[]` | array | `terraform` collector (`aws-resources-tagged`, `entity-ref-valid`) |
| `.iac.refs` | object | `terraform` collector, only when `backstage_url` is set (`entity-ref-valid` referential integrity) |

**Note:** Ensure the `terraform` collector is configured before enabling this policy. For `entity-ref-valid`'s existence check, also set the collector's `backstage_url` (and `BACKSTAGE_TOKEN` if required). All inputs (including the tagging inputs `required_tags`, `entity_ref_tag_key`, `entity_ref_kind`, and `exempt_resource_types`) are documented in `lunar-policy.yml`.

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

### Require an `entity_ref` tag on every resource, verified against Backstage

Block a PR (or score a component) when any AWS resource is missing a
`backstage.com/entity_ref` tag, and validate that the value resolves in the
Backstage catalog:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/terraform@main
    on: [infra]
    with:
      entity_ref_tag_key: "backstage.com/entity_ref"
      backstage_url: "https://backstage.example.com"   # enables referential integrity
    secrets:
      BACKSTAGE_TOKEN: "backstage-api-token"

policies:
  - uses: github://earthly/lunar-lib/policies/terraform@main
    on: [infra]
    enforcement: report-pr          # or score
    include: [aws-resources-tagged, entity-ref-valid]
    with:
      required_tags: "backstage.com/entity_ref"
      entity_ref_tag_key: "backstage.com/entity_ref"
      entity_ref_kind: "component"  # optional: require a component ref
```

Leave `backstage_url` unset to keep `entity-ref-valid` as a format-only check
(no catalog lookups).

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

### Tagging example (`aws-resources-tagged` + `entity-ref-valid`)

With `required_tags: backstage.com/entity_ref`, given the normalized module view:

```json
{
  "iac": {
    "modules": [
      {
        "path": "deploy/terraform",
        "resources": [
          {"type": "aws_db_instance", "name": "main", "category": "datastore",
           "tags": {"backstage.com/entity_ref": "component:default/payment-api"}},
          {"type": "aws_s3_bucket", "name": "logs", "category": "datastore"},
          {"type": "aws_lb", "name": "api", "category": "network", "tags_expression": true}
        ],
        "default_tags": {}
      }
    ],
    "refs": {
      "checked": true,
      "entity_refs": [{"name": "component:default/payment-api", "exists": true}]
    }
  }
}
```

- `aws_db_instance.main` — **passes** both checks (tag present, value resolves in Backstage).
- `aws_s3_bucket.logs` — **fails** `aws-resources-tagged` (no `backstage.com/entity_ref`, and none via `default_tags`).
- `aws_lb.api` — **skipped** by `aws-resources-tagged` (`tags_expression`: keys can't be extracted from `merge(...)`).

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
4. **For `aws-resources-tagged` failures:** Add the required tag key to the resource, or set it once for the whole module via provider `default_tags`:
   ```hcl
   # Per-resource
   resource "aws_s3_bucket" "logs" {
     bucket = "acme-logs"
     tags = {
       "backstage.com/entity_ref" = "component:default/payment-api"
     }
   }

   # Or module-wide via the provider
   provider "aws" {
     default_tags {
       tags = {
         "backstage.com/entity_ref" = "component:default/payment-api"
       }
     }
   }
   ```
5. **For `entity-ref-valid` failures:** Make the tag value a well-formed Backstage entity reference (`[<kind>:][<namespace>/]<name>`, e.g. `component:default/payment-api`) that names an entity registered in the Backstage catalog.
