"""Forbid unrestricted public ingress to the PostgreSQL port."""

from lunar_policy import Check, variable_or_default
from helpers import public_ingress_offenders, has_any_security_group


def main(node=None):
    c = Check("security-group-no-public-postgres", "No public ingress to PostgreSQL", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        if not has_any_security_group(native):
            c.skip("No security groups found")

        port = int(variable_or_default("postgres_port", "5432"))
        offenders = public_ingress_offenders(native, port)
        if offenders:
            c.fail(
                "Unrestricted (0.0.0.0/0 or ::/0) ingress to PostgreSQL port {} in: {}. "
                "Restrict the source to known CIDRs or security groups.".format(
                    port, ", ".join(offenders)
                )
            )
    return c


if __name__ == "__main__":
    main()
