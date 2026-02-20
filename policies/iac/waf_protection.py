"""Require WAF protection for internet-facing services."""

from lunar_policy import Check
from helpers import is_internet_accessible, has_waf_protection


def main(node=None):
    c = Check("waf-protection", "Internet-facing services have WAF", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        if is_internet_accessible(native):
            c.assert_true(
                has_waf_protection(native),
                "Service has internet-facing resources but no WAF protection configured",
            )
    return c


if __name__ == "__main__":
    main()
