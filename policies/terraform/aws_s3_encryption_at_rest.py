"""Require S3 buckets to declare server-side encryption at rest.

S3 applies SSE-S3 by default, but SOC 2 evidence wants an explicit, auditable
encryption configuration per bucket (so key management is a deliberate choice,
not an implicit default).
"""

from lunar_policy import Check
from helpers import iter_resources, references, block


def main(node=None):
    c = Check("aws-s3-encryption-at-rest", "S3 buckets declare encryption at rest", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        buckets = list(iter_resources(native, "aws_s3_bucket"))
        if not buckets:
            c.skip("No S3 buckets found")

        sse = list(iter_resources(native, "aws_s3_bucket_server_side_encryption_configuration"))
        for _, bname, bcfg in buckets:
            # Legacy inline server_side_encryption_configuration block counts.
            if block(bcfg, "server_side_encryption_configuration"):
                continue
            covered = any(references(s.get("bucket"), "aws_s3_bucket", bname) for _, _, s in sse)
            if not covered:
                c.fail(
                    "aws_s3_bucket.{} has no aws_s3_bucket_server_side_encryption_"
                    "configuration. Declare SSE explicitly.".format(bname)
                )
    return c


if __name__ == "__main__":
    main()
