import re
import sys

sys.path.insert(0, ".")
from helpers import get_sbom_components
from lunar_policy import Check, variable_or_default


def check_disallowed_packages(node=None):
    c = Check(
        "disallowed-packages",
        "Checks for disallowed packages by PURL, name, or group pattern",
        node=node,
    )
    with c:
        patterns_str = variable_or_default("disallowed_packages", "")
        patterns = [p.strip() for p in patterns_str.split(",") if p.strip()]

        if not patterns:
            pass  # No patterns configured — auto-pass
        else:
            try:
                regexes = [re.compile(p, re.IGNORECASE) for p in patterns]
            except re.error as e:
                raise ValueError(f"Invalid regex in disallowed_packages: {e}")

            components, has_sbom = get_sbom_components(c)
            if not has_sbom:
                c.skip("No SBOM data available")

            for component in components:
                name = component.get_value_or_default(".name", "")
                purl = component.get_value_or_default(".purl", "")
                group = component.get_value_or_default(".group", "")

                targets = [t for t in [purl, name, group] if t]

                for target in targets:
                    for regex in regexes:
                        if regex.search(target):
                            c.fail(
                                f"Package '{name or purl}' matches disallowed "
                                f"pattern '{regex.pattern}'"
                            )
                            break
    return c


if __name__ == "__main__":
    check_disallowed_packages()
