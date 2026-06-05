"""Forbid S3 buckets from granting public access through ACLs."""

from lunar_policy import Check
from helpers import iter_resources, block


_PUBLIC_ACLS = ("public-read", "public-read-write")
_PUBLIC_GROUPS = ("AllUsers", "AuthenticatedUsers")


def main(node=None):
    c = Check("aws-s3-no-public-acl", "S3 buckets do not grant public ACL access", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        buckets = list(iter_resources(native, "aws_s3_bucket"))
        if not buckets:
            c.skip("No S3 buckets found")

        # Standalone aws_s3_bucket_acl: canned ACL or explicit public grants.
        for _, name, cfg in iter_resources(native, "aws_s3_bucket_acl"):
            acl = cfg.get("acl")
            if isinstance(acl, str) and acl in _PUBLIC_ACLS:
                c.fail("aws_s3_bucket_acl.{} sets acl = \"{}\".".format(name, acl))
            for pol in block(cfg, "access_control_policy"):
                for grant in block(pol, "grant"):
                    for grantee in block(grant, "grantee"):
                        uri = str(grantee.get("uri", ""))
                        if any(g in uri for g in _PUBLIC_GROUPS):
                            c.fail(
                                "aws_s3_bucket_acl.{} grants access to a public "
                                "group ({}).".format(name, uri)
                            )

        # Legacy inline canned ACL on the bucket itself.
        for _, bname, bcfg in buckets:
            acl = bcfg.get("acl")
            if isinstance(acl, str) and acl in _PUBLIC_ACLS:
                c.fail("aws_s3_bucket.{} sets acl = \"{}\".".format(bname, acl))
    return c


if __name__ == "__main__":
    main()
