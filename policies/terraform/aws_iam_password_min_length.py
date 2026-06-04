"""Require an IAM account password policy with a sufficient minimum length.

Account-scoped control: the IAM account password policy is a global singleton,
so — like the CloudTrail and GuardDuty checks — absence IS the violation. Apply
this check to the component that owns the account baseline.
"""

from lunar_policy import Check, variable_or_default
from helpers import iter_resources, as_int


def main(node=None):
    c = Check("aws-iam-password-min-length", "IAM password policy enforces a minimum length", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        min_len = as_int(variable_or_default("min_password_length", "14")) or 14

        policies = list(iter_resources(native, "aws_iam_account_password_policy"))
        if not policies:
            c.fail(
                "No aws_iam_account_password_policy found. Define one with "
                "minimum_password_length >= {}.".format(min_len)
            )
            return c

        for _, name, cfg in policies:
            n = as_int(cfg.get("minimum_password_length"))
            if n is None or n < min_len:
                c.fail(
                    "aws_iam_account_password_policy.{} has minimum_password_length "
                    "= {} (require >= {}).".format(name, n if n is not None else "unset", min_len)
                )
    return c


if __name__ == "__main__":
    main()
