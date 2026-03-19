import re
import sys

sys.path.insert(0, ".")
from helpers import get_sbom_components, parse_patterns
from lunar_policy import Check, variable_or_default


def check_disallowed_packages(node=None):
    c = Check(
        "disallowed-packages",
        "Checks for disallowed packages by PURL, name, or group pattern",
        node=node,
    )
    with c:
        patterns_str = variable_or_default("disallowed_packages", "")
        patterns = parse_patterns(patterns_str)

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

            seen = set()
            for component in components:
                name = component.get_value_or_default(".name", "")
                purl = component.get_value_or_default(".purl", "")
                group = component.get_value_or_default(".group", "")

                key = purl or name
                if key in seen:
                    continue

                targets = [t for t in [purl, name, group] if t]
                matched = False

                for target in targets:
                    if matched:
                        break
                    for regex in regexes:
                        if regex.search(target):
                            c.fail(
                                f"Package '{name or purl}' matches disallowed "
                                f"pattern '{regex.pattern}'"
                            )
                            seen.add(key)
                            matched = True
                            break
    return c


if __name__ == "__main__":
    check_disallowed_packages()
