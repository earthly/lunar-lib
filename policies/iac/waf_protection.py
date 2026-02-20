"""Require WAF protection for internet-facing services."""

from lunar_policy import Check
from helpers import get_modules


def main(node=None):
    c = Check("waf-protection", "Internet-facing services have WAF", node=node)
    with c:
        modules = get_modules(c)

        for mod in modules:
            path = mod.get_value_or_default(".path", ".")
            analysis = mod.get_node(".analysis")
            if not analysis.exists():
                continue

            internet_accessible = analysis.get_value_or_default(".internet_accessible", False)
            if internet_accessible:
                has_waf = analysis.get_value_or_default(".has_waf", False)
                if not has_waf:
                    c.fail(f"Module '{path}': internet-facing resources without WAF protection")
    return c


if __name__ == "__main__":
    main()
