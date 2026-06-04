"""Require CloudTrail trails to encrypt logs with a KMS key.

Trail *absence* is owned by aws-cloudtrail-multi-region; this check refines an
existing trail, so it skips when no trail is present.
"""

from lunar_policy import Check
from helpers import iter_resources


def main(node=None):
    c = Check("aws-cloudtrail-kms-encryption", "CloudTrail logs are encrypted with KMS", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        trails = list(iter_resources(native, "aws_cloudtrail"))
        if not trails:
            c.skip("No CloudTrail trails found")

        for _, name, cfg in trails:
            if not cfg.get("kms_key_id"):
                c.fail(
                    "aws_cloudtrail.{} has no kms_key_id. Encrypt delivered logs "
                    "with a KMS customer-managed key.".format(name)
                )
    return c


if __name__ == "__main__":
    main()
