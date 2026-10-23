"""Require every IAM role to carry a permissions boundary."""

from lunar_policy import Check
from helpers import iter_resources


def main(node=None):
    c = Check(
        "aws-iam-role-permissions-boundary",
        "IAM roles set a permissions boundary",
        node=node,
    )
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        offenders = []
        found = False

        for _, name, cfg in iter_resources(native, "aws_iam_role"):
            found = True
            boundary = cfg.get("permissions_boundary")
            # An empty string is as unbounded as an absent attribute.
            if not (isinstance(boundary, str) and boundary.strip()):
                offenders.append("aws_iam_role.{}".format(name))

        if not found:
            c.skip("No IAM roles found")

        if offenders:
            c.fail(
                "IAM roles without a permissions boundary: {}. Set "
                "permissions_boundary to the policy ARN that caps what the "
                "role can ever be granted.".format(", ".join(sorted(set(offenders))))
            )
    return c


if __name__ == "__main__":
    main()
