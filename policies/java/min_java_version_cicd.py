from lunar_policy import Check, variable_or_default

from min_java_version import parse_java_minimum, report_ci_versions


def check_min_java_version_cicd(min_version=None, node=None):
    """Check that every Java version recorded in CI meets the minimum."""
    if min_version is None:
        min_version = variable_or_default("min_java_version_cicd", "17")

    c = Check("min-java-version-cicd", "Ensures CI/CD Java version meets minimum", node=node)
    with c:
        cmds_node = c.get_node(".lang.java.cicd.cmds")
        if not cmds_node.exists():
            c.skip("No java or javac commands recorded in CI")
        cmds = cmds_node.get_value()
        if not cmds:
            c.skip("No java or javac commands recorded in CI")

        try:
            minimum = parse_java_minimum(min_version)
        except ValueError as e:
            c.fail(f"min_java_version_cicd {e}")
            return c

        report_ci_versions(c, cmds, minimum, f"CI ran Java that does not meet {minimum.describe()}")
    return c


if __name__ == "__main__":
    check_min_java_version_cicd()
