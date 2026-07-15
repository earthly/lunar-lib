from lunar_policy import Check, variable_or_default


def check_min_kotlin_version(min_version=None, node=None):
    """Check that the Kotlin compiler version meets the configured minimum."""
    if min_version is None:
        min_version = variable_or_default("min_kotlin_version", "1.8")

    c = Check(
        "min-kotlin-version",
        "Ensures the Kotlin compiler version meets the configured minimum",
        node=node,
    )
    with c:
        kotlin = c.get_node(".lang.kotlin")
        if not kotlin.exists():
            c.skip("Not a Kotlin project")
        project_exists_node = kotlin.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Kotlin project detected in this component")

        version_node = kotlin.get_node(".version")
        if not version_node.exists():
            c.skip("Kotlin version not detected")

        actual_version = version_node.get_value()
        if not actual_version or not str(actual_version).strip():
            c.skip("Kotlin version not detected")

        def parse_version(v):
            # Tolerate suffixes like "2.0.0-Beta1" / "1.9.22-RC" — take the
            # leading digits of each dot-separated segment, stop at the first
            # non-numeric segment.
            parts = []
            for seg in str(v).strip().split("."):
                digits = ""
                for ch in seg:
                    if ch.isdigit():
                        digits += ch
                    else:
                        break
                if digits == "":
                    break
                parts.append(int(digits))
            if not parts:
                raise ValueError(f"no numeric components in {v!r}")
            return tuple(parts)

        try:
            actual = parse_version(actual_version)
            minimum = parse_version(min_version)
            cmp_len = max(len(actual), len(minimum))
            actual_padded = actual + (0,) * (cmp_len - len(actual))
            minimum_padded = minimum + (0,) * (cmp_len - len(minimum))

            c.assert_true(
                actual_padded >= minimum_padded,
                f"Kotlin version {actual_version} is below minimum {min_version}. "
                f"Update the Kotlin plugin version to {min_version} or higher.",
            )
        except (ValueError, TypeError):
            c.fail(f"Could not parse Kotlin version: {actual_version}")
    return c


if __name__ == "__main__":
    check_min_kotlin_version()
