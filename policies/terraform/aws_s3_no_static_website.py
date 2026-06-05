"""Forbid S3 buckets from serving a public static website."""

from lunar_policy import Check
from helpers import iter_resources, block


def main(node=None):
    c = Check("aws-s3-no-static-website", "S3 buckets do not host static websites", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        buckets = list(iter_resources(native, "aws_s3_bucket"))
        if not buckets:
            c.skip("No S3 buckets found")

        for _, name, _ in iter_resources(native, "aws_s3_bucket_website_configuration"):
            c.fail(
                "aws_s3_bucket_website_configuration.{} enables static website "
                "hosting, which serves bucket contents publicly.".format(name)
            )

        # Legacy inline website block on the bucket itself.
        for _, bname, bcfg in buckets:
            if block(bcfg, "website"):
                c.fail(
                    "aws_s3_bucket.{} has an inline website block (static "
                    "hosting).".format(bname)
                )
    return c


if __name__ == "__main__":
    main()
