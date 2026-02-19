# Terraform Guardrails

Enforces Terraform-specific configuration best practices.

## Overview

This policy enforces Terraform-specific standards that don't transfer to other IaC frameworks: provider version pinning, module version pinning, and remote backend usage. It reads from `.iac.native.terraform.files[]` and analyzes the parsed HCL to extract `required_providers`, `module`, and `backend` blocks. For generic IaC checks (validity, WAF, datastores), see the `iac` policy.

## Policies

This policy provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `provider-versions-pinned` | Providers specify version constraints | Provider in `required_providers` has no `version` field |
| `module-versions-pinned` | Modules use pinned versions | Module missing `version` or `?ref=` in source |
| `remote-backend` | Remote backend configured | No `terraform { backend {} }` block found |

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
