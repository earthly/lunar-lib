"""Require CloudTrail trails to enable log-file integrity validation.

Trail *absence* is owned by aws-cloudtrail-multi-region; this check refines an
existing trail, so it skips when no trail is present.
"""

from lunar_policy import Check
from helpers import iter_resources, truthy


def main(node=None):
    c = Check("aws-cloudtrail-log-file-validation", "CloudTrail validates log-file integrity", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        trails = list(iter_resources(native, "aws_cloudtrail"))
        if not trails:
            c.skip("No CloudTrail trails found")

        for _, name, cfg in trails:
            if not truthy(cfg.get("enable_log_file_validation", False)):
                c.fail(
                    "aws_cloudtrail.{} does not set enable_log_file_validation = "
                    "true. Enable it to detect tampering with delivered logs.".format(name)
                )
    return c


if __name__ == "__main__":
    main()
