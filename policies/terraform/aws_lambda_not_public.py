"""Forbid Lambda functions from being publicly invokable."""

from lunar_policy import Check
from helpers import iter_resources


def main(node=None):
    c = Check("aws-lambda-not-public", "Lambda functions are not publicly invokable", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        functions = list(iter_resources(native, "aws_lambda_function"))
        permissions = list(iter_resources(native, "aws_lambda_permission"))
        urls = list(iter_resources(native, "aws_lambda_function_url"))
        if not functions and not permissions and not urls:
            c.skip("No Lambda resources found")

        for _, name, cfg in permissions:
            principal = str(cfg.get("principal", ""))
            # "*" grants invoke to everyone unless scoped by source_account,
            # source_arn, or principal_org_id (org-internal — not public).
            scoped = cfg.get("source_account") or cfg.get("source_arn") or cfg.get("principal_org_id")
            if principal == "*" and not scoped:
                c.fail(
                    "aws_lambda_permission.{} grants invoke to principal \"*\" with no "
                    "source_account/source_arn/principal_org_id scope (publicly "
                    "invokable).".format(name)
                )

        for _, name, cfg in urls:
            if str(cfg.get("authorization_type", "")).upper() == "NONE":
                c.fail(
                    "aws_lambda_function_url.{} sets authorization_type = NONE "
                    "(unauthenticated public URL).".format(name)
                )
    return c


if __name__ == "__main__":
    main()
