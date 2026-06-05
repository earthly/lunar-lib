"""Require ACM certificates to use DNS validation."""

from lunar_policy import Check
from helpers import iter_resources


def main(node=None):
    c = Check("aws-acm-cert-dns-validation", "ACM certificates use DNS validation", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        certs = list(iter_resources(native, "aws_acm_certificate"))
        if not certs:
            c.skip("No ACM certificates found")

        for _, name, cfg in certs:
            # Imported certs (private_key/certificate_body) are not validated by ACM.
            if cfg.get("private_key") or cfg.get("certificate_body"):
                continue
            method = cfg.get("validation_method")
            if method != "DNS":
                c.fail(
                    "aws_acm_certificate.{} uses validation_method = {}; use DNS "
                    "validation so renewals are automatic and auditable.".format(
                        name, "\"{}\"".format(method) if method else "unset"
                    )
                )
    return c


if __name__ == "__main__":
    main()
