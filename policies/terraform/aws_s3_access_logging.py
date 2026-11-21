"""Require S3 buckets to have server access logging enabled."""

from lunar_policy import Check
from helpers import iter_resources, references, block


def resource_presence(cfg):
    """Literal instance presence, or None when source HCL needs evaluation."""
    if "count" in cfg and "for_each" in cfg:
        return None
    if "count" in cfg:
        count = cfg["count"]
        if type(count) is int and count >= 0:
            return count > 0
        return None
    if "for_each" in cfg:
        instances = cfg["for_each"]
        if isinstance(instances, dict) and not any("${" in key for key in instances):
            return bool(instances)
        return None
    return True


def main(node=None):
    c = Check("aws-s3-access-logging", "S3 buckets have server access logging", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        buckets = list(iter_resources(native, "aws_s3_bucket"))
        if not buckets:
            c.skip("No S3 buckets found")

        loggings = list(iter_resources(native, "aws_s3_bucket_logging"))
        unverified = []
        failed = False
        active = False
        for _, bname, cfg in buckets:
            presence = resource_presence(cfg)
            if presence is False:
                continue
            if presence is None:
                unverified.append("aws_s3_bucket.{} instance condition".format(bname))
                continue
            active = True
            inline = any(b.get("target_bucket") for b in block(cfg, "logging"))
            candidates = [
                resource_presence(lg)
                for _, _, lg in loggings
                if references(lg.get("bucket"), "aws_s3_bucket", bname)
                and lg.get("target_bucket")
            ]
            separate = any(presence is True for presence in candidates)
            if not (inline or separate) and None in candidates:
                unverified.append("aws_s3_bucket.{} logging condition".format(bname))
                continue
            if not (inline or separate):
                failed = True
                c.fail(
                    "aws_s3_bucket.{} has no active server access logging with a target "
                    "(inline logging block or an aws_s3_bucket_logging resource).".format(bname)
                )
        if unverified:
            message = "UNVERIFIED: source HCL cannot evaluate {}. Review the tenant plan and live delivery.".format(
                "; ".join(unverified)
            )
            if failed:
                # Check.skip clears earlier failures, so preserve known violations.
                c.fail(message)
            else:
                c.skip(message)
        elif not active:
            c.skip("No active S3 buckets found")
    return c


if __name__ == "__main__":
    main()
