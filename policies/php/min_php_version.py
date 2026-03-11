from lunar_policy import Check, variable_or_default


def check_min_php_version(min_version=None, node=None):
    """Check that the PHP version constraint meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_php_version", "8.1")

    c = Check("min-php-version", "Ensures PHP version meets minimum", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")

        version_node = php.get_node(".php_version")
        if not version_node.exists():
            c.skip("PHP version constraint not detected in composer.json")

        raw_version = str(version_node.get_value())

        # Extract the lowest version from a constraint like "^8.2", ">=8.1", "~8.2.0", "8.2.*"
        def extract_base_version(constraint):
            """Extract the base version number from a PHP version constraint."""
            v = constraint.strip()
            # Strip common constraint prefixes
            for prefix in ["^", ">=", ">", "~", "<=", "<", "="]:
                if v.startswith(prefix):
                    v = v[len(prefix):]
                    break
            # Handle OR constraints (||) — take the first
            if "||" in v:
                v = v.split("||")[0].strip()
            # Handle AND constraints (space or comma) — take the first
            for sep in [" ", ","]:
                if sep in v:
                    v = v.split(sep)[0].strip()
            # Remove wildcard
            v = v.replace(".*", "").replace("*", "")
            # Strip any remaining constraint prefixes after split
            for prefix in ["^", ">=", ">", "~", "<=", "<", "="]:
                if v.startswith(prefix):
                    v = v[len(prefix):]
            return v.strip()

        def parse_version(v):
            parts = str(v).split(".")
            return tuple(int(p) for p in parts if p.isdigit())

        try:
            base_version = extract_base_version(raw_version)
            actual = parse_version(base_version)
            minimum = parse_version(min_version)

            if not actual:
                c.skip(f"Could not parse PHP version constraint: {raw_version}")

            # Pad to same length for correct comparison
            cmp_len = max(len(actual), len(minimum))
            actual_padded = actual + (0,) * (cmp_len - len(actual))
            minimum_padded = minimum + (0,) * (cmp_len - len(minimum))

            c.assert_true(
                actual_padded >= minimum_padded,
                f"PHP version constraint '{raw_version}' allows versions below minimum {min_version}. "
                f"Update the php requirement in composer.json to '^{min_version}' or higher."
            )
        except (ValueError, TypeError):
            c.fail(f"Could not parse PHP version constraint: {raw_version}")
    return c


if __name__ == "__main__":
    check_min_php_version()
