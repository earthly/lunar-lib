"""Require S3 buckets to have server access logging enabled."""

import json
import posixpath
import re

from lunar_policy import Check, variable_or_default
from helpers import as_blocks, references, block


def scoped_resources(native, rtype):
    """Keep resource identity and references scoped to their Terraform module."""
    for f in native:
        path = f.get_value_or_default(".path", "")
        raw = f.get_value_or_default(".hcl", {})
        for name, configs in raw.get("resource", {}).get(rtype, {}).items():
            for cfg in as_blocks(configs):
                yield path, name, cfg


def terminal_exceptions():
    """Explicit file/resource identities mapped to durable approval reasons."""
    value = json.loads(variable_or_default("s3_terminal_log_destinations", "{}"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    for key, reason in value.items():
        if not re.fullmatch(r"[A-Za-z0-9_./-]+\.(tf|tofu):aws_s3_bucket\.[A-Za-z_][A-Za-z0-9_-]*", key):
            raise ValueError("keys must be exact relative file:aws_s3_bucket.name identities")
        path = key.split(":")[0]
        if path.startswith("/") or posixpath.normpath(path) != path or ".." in path.split("/"):
            raise ValueError("exception paths must be canonical and repository-relative")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("each exception requires an approval reason or reference")
    return value


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

        try:
            exceptions = terminal_exceptions()
        except (ValueError, TypeError) as exc:
            c.fail("Invalid s3_terminal_log_destinations: {}".format(exc))
            return c

        buckets = list(scoped_resources(native, "aws_s3_bucket"))
        if not buckets:
            if exceptions:
                c.fail("Terminal log destination exceptions did not match any S3 buckets.")
                return c
            c.skip("No S3 buckets found")

        loggings = list(scoped_resources(native, "aws_s3_bucket_logging"))
        unverified = []
        failed = False
        active = False
        matched = set()
        for path, bname, cfg in buckets:
            identity = "{}:aws_s3_bucket.{}".format(path, bname)
            local_loggings = [lg for lg_path, _, lg in loggings if posixpath.dirname(lg_path) == posixpath.dirname(path)]
            if identity in exceptions:
                matched.add(identity)
            presence = resource_presence(cfg)
            if presence is False:
                continue
            if identity in exceptions:
                incoming = any(
                    resource_presence(lg) is not False
                    and references(lg.get("target_bucket"), "aws_s3_bucket", bname)
                    and lg.get("bucket")
                    and not references(lg.get("bucket"), "aws_s3_bucket", bname)
                    for lg in local_loggings
                )
                if incoming:
                    continue
                failed = True
                c.fail("{} exception is not a referenced terminal log destination.".format(identity))
                continue
            active = True
            inline = any(b.get("target_bucket") for b in block(cfg, "logging"))
            candidates = [
                resource_presence(lg)
                for lg in local_loggings
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
        for identity in sorted(exceptions.keys() - matched):
            failed = True
            c.fail("Terminal log destination exception did not match {}.".format(identity))
        if unverified:
            message = "UNVERIFIED: source HCL cannot evaluate {}. Review the tenant plan and live delivery.".format(
                "; ".join(unverified)
            )
            if matched:
                message += " Explicit terminal exceptions: {}.".format("; ".join(sorted(matched)))
            if failed:
                # Check.skip clears earlier failures, so preserve known violations.
                c.fail(message)
            else:
                c.skip(message)
        elif not active and not failed:
            c.skip("No non-exempt active S3 buckets found")
    return c


if __name__ == "__main__":
    main()
