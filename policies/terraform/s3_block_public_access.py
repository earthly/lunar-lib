"""Require S3 buckets to block public access."""

from lunar_policy import Check
from helpers import iter_resources, references, truthy


_FLAGS = ("block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets")


def main(node=None):
    c = Check("s3-block-public-access", "S3 buckets block public access", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        buckets = list(iter_resources(native, "aws_s3_bucket"))
        if not buckets:
            c.skip("No S3 buckets found")

        # An account-level block covers every bucket.
        for _, _, cfg in iter_resources(native, "aws_s3_account_public_access_block"):
            if all(truthy(cfg.get(f, False)) for f in _FLAGS):
                return c

        pabs = list(iter_resources(native, "aws_s3_bucket_public_access_block"))
        for _, bname, _ in buckets:
            covered = any(
                references(pab.get("bucket"), "aws_s3_bucket", bname)
                and all(truthy(pab.get(f, False)) for f in _FLAGS)
                for _, _, pab in pabs
            )
            if not covered:
                c.fail(
                    "aws_s3_bucket.{} has no aws_s3_bucket_public_access_block with all "
                    "four block flags = true.".format(bname)
                )
    return c


if __name__ == "__main__":
    main()
