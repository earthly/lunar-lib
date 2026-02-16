from lunar_policy import Check, variable_or_default


def check_min_java_version(min_version=None, node=None):
    """Check that Java version meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_java_version", "17")

    c = Check("min-java-version", "Ensures Java version meets minimum", node=node)
    with c:
        java = c.get_node(".lang.java")
        if not java.exists():
            c.skip("Not a Java project")

        version_node = java.get_node(".version")
        if not version_node.exists():
            c.skip("Java version not detected in build config")

        actual_version = version_node.get_value()

        # Java versions are major numbers (8, 11, 17, 21) — integer comparison
        try:
            actual = int(str(actual_version).strip())
            minimum = int(str(min_version).strip())

            c.assert_true(
                actual >= minimum,
                f"Java version {actual} is below minimum {minimum}. "
                f"Update your build config to target Java {minimum} or higher."
            )
        except (ValueError, TypeError):
            c.fail(f"Could not parse Java version: {actual_version}")
    return c


if __name__ == "__main__":
    check_min_java_version()
