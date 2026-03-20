import re

from lunar_policy import Check, variable_or_default


def check_min_version(min_version=None, node=None):
    """Check that PHP version constraint meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_version", "8.1")

    c = Check("min-version", "Ensures PHP version meets minimum", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")
        if not php.get_node(".project_exists").exists():
            c.skip("No PHP project detected in this component")

        version_node = php.get_node(".version")
        if not version_node.exists():
            c.skip("PHP version constraint not detected")

        constraint = version_node.get_value()
        if not constraint:
            c.skip("PHP version constraint is empty")

        def parse_version(v):
            """Parse a version string like '8.1' or '8.1.0' into a tuple."""
            parts = re.findall(r'\d+', str(v))
            return tuple(int(p) for p in parts)

        def extract_min_from_constraint(constraint_str):
            """Extract the minimum version from a PHP version constraint.

            Handles common patterns:
            - ^8.1 or ^8.1.0 (caret: >=8.1.0 <9.0.0)
            - ~8.1 (tilde: >=8.1.0 <8.2.0)
            - >=8.1
            - 8.1.* or 8.*
            - ^7.4 || ^8.1 (OR constraint: takes lowest)
            - >=8.1 <9.0 (AND constraint: takes the lower bound)
            """
            # Handle OR constraints — split on || and take the lowest version
            if "||" in constraint_str:
                parts = constraint_str.split("||")
                versions = []
                for part in parts:
                    v = extract_min_from_constraint(part.strip())
                    if v is not None:
                        versions.append(v)
                return min(versions) if versions else None

            # Strip leading operators and extract version number
            cleaned = constraint_str.strip()

            # Match version with optional operator prefix
            match = re.search(r'[\^~>=<]*\s*(\d+(?:\.\d+)*)', cleaned)
            if not match:
                return None

            return parse_version(match.group(1))

        try:
            minimum = parse_version(min_version)
            actual = extract_min_from_constraint(constraint)

            if actual is None:
                c.fail(f"Could not parse PHP version constraint: {constraint}")
                return c

            # Compare only as many components as minimum specifies
            c.assert_true(
                actual[:len(minimum)] >= minimum,
                f"PHP version {constraint} (min {'.'.join(str(p) for p in actual)}) "
                f"is below minimum {min_version}. Update the PHP constraint in composer.json."
            )
        except (ValueError, TypeError):
            c.fail(f"Could not parse PHP version constraint: {constraint}")
    return c


if __name__ == "__main__":
    check_min_version()
