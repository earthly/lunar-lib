"""Require a multi-region CloudTrail trail that ships to CloudWatch Logs."""

from lunar_policy import Check, variable_or_default
from helpers import iter_resources, truthy


def main(node=None):
    c = Check("cloudtrail-multi-region", "CloudTrail is multi-region and ships to CloudWatch", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        require_cw = variable_or_default("require_cloudtrail_cloudwatch", "true").strip().lower() == "true"

        trails = list(iter_resources(native, "aws_cloudtrail"))
        if not trails:
            # Account-scoped control: absence IS the violation. Apply this check
            # to the component that owns the account baseline.
            c.fail(
                "No aws_cloudtrail found. Enable a multi-region CloudTrail trail "
                "for account-wide API audit logging."
            )
            return c

        for _, _, cfg in trails:
            if not truthy(cfg.get("is_multi_region_trail", False)):
                continue
            if require_cw and not cfg.get("cloud_watch_logs_group_arn"):
                continue
            return c  # a compliant trail exists

        need = "is_multi_region_trail = true"
        if require_cw:
            need += " and cloud_watch_logs_group_arn"
        c.fail("No CloudTrail trail sets {}.".format(need))
    return c


if __name__ == "__main__":
    main()
