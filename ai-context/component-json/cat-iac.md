# Category: `.iac`

Infrastructure as Code. Normalized across Terraform, Pulumi, CloudFormation, etc.

```json
{
  "iac": {
    "source": {
      "tool": "hcl2json",
      "version": "0.6.4"
    },
    "files": [
      {"path": "main.tf", "valid": true},
      {"path": "variables.tf", "valid": true}
    ],
    "native": {
      "terraform": {
        "files": [
          {
            "path": "main.tf",
            "hcl": {
              "terraform": [
                {
                  "required_providers": [{"aws": {"version": "~> 5.0"}}],
                  "backend": [{"s3": {"bucket": "my-state"}}]
                }
              ],
              "resource": {
                "aws_db_instance": {"main": [{"engine": "postgres", "lifecycle": [{"prevent_destroy": true}]}]},
                "aws_lb": {"api": [{"internal": false}]},
                "aws_wafv2_web_acl": {"main": [{}]},
                "aws_wafv2_web_acl_association": {"api": [{}]}
              },
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

## Key Policy Paths

- `.iac.files[].valid` — Config files valid
- `.iac.native.terraform.files[].hcl` — Full parsed HCL for policy analysis
- `.iac.native.terraform.files[].hcl.resource` — Terraform resources (WAF, datastores, etc.)
- `.iac.native.terraform.files[].hcl.terraform` — Provider versions, backend config
- `.iac.native.terraform.files[].hcl.module` — Module sources and versions
