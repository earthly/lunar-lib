"""Require S3 buckets to have server access logging enabled."""

from lunar_policy import Check
from helpers import iter_resources, references, block


def main(node=None):
    c = Check("s3-access-logging", "S3 buckets have server access logging", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        buckets = list(iter_resources(native, "aws_s3_bucket"))
        if not buckets:
            c.skip("No S3 buckets found")

        loggings = list(iter_resources(native, "aws_s3_bucket_logging"))
        for _, bname, cfg in buckets:
            inline = any(b.get("target_bucket") for b in block(cfg, "logging"))
            separate = any(
                references(lg.get("bucket"), "aws_s3_bucket", bname) for _, _, lg in loggings
            )
            if not (inline or separate):
                c.fail(
                    "aws_s3_bucket.{} has no server access logging (inline logging block "
                    "or an aws_s3_bucket_logging resource).".format(bname)
                )
    return c


if __name__ == "__main__":
    main()
