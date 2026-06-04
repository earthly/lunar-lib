"""Forbid attaching IAM policies directly to users (use groups or roles)."""

from lunar_policy import Check
from helpers import iter_resources, has_resource


def main(node=None):
    c = Check("aws-iam-no-direct-user-policies", "No IAM policies attached directly to users", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        if not has_resource(
            native,
            "aws_iam_user",
            "aws_iam_user_policy",
            "aws_iam_user_policy_attachment",
            "aws_iam_policy_attachment",
        ):
            c.skip("No IAM user resources found")

        for _, name, _ in iter_resources(native, "aws_iam_user_policy"):
            c.fail(
                "aws_iam_user_policy.{} attaches an inline policy directly to a "
                "user. Attach policies to a group or role instead.".format(name)
            )

        for _, name, _ in iter_resources(native, "aws_iam_user_policy_attachment"):
            c.fail(
                "aws_iam_user_policy_attachment.{} attaches a managed policy "
                "directly to a user. Use a group or role.".format(name)
            )

        for _, name, cfg in iter_resources(native, "aws_iam_policy_attachment"):
            if cfg.get("users"):
                c.fail(
                    "aws_iam_policy_attachment.{} attaches a policy to users "
                    "directly. Attach via groups or roles only.".format(name)
                )
    return c


if __name__ == "__main__":
    main()
