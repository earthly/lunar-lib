"""Require DynamoDB tables to declare server-side encryption explicitly.

DynamoDB is always encrypted at rest with an AWS-owned key by default. This
check enforces an explicit ``server_side_encryption { enabled = true }`` block
so encryption (optionally with a customer-managed KMS key) is a deliberate,
auditable choice rather than an implicit default.
"""

from lunar_policy import Check
from helpers import iter_resources, block, truthy


def main(node=None):
    c = Check("aws-dynamodb-encryption", "DynamoDB tables declare encryption at rest", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        tables = list(iter_resources(native, "aws_dynamodb_table"))
        if not tables:
            c.skip("No DynamoDB tables found")

        for _, name, cfg in tables:
            sse = block(cfg, "server_side_encryption")
            if not sse or not any(truthy(s.get("enabled", False)) for s in sse):
                c.fail(
                    "aws_dynamodb_table.{} has no server_side_encryption {{ enabled "
                    "= true }} block. Declare encryption explicitly.".format(name)
                )
    return c


if __name__ == "__main__":
    main()
