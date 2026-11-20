from lunar_policy import Check, variable_or_default

from min_java_version import parse_java_minimum, report_ci_versions

NO_EVIDENCE = (
    "No Java version was recorded in CI for this Java project, so its JDK can't be checked. "
    "Run its CI build on runners with the Lunar CI/CD Tracer, and enable the java collector's "
    "cicd sub-collector."
)


def parse_require(value):
    """Parse the require_java_version_cicd input; raise ValueError unless it is "true" or "false"."""
    text = str(value).strip().lower()
    if text in ("", "false"):
        return False
    if text == "true":
        return True
    raise ValueError(f'must be "true" or "false", got "{value}"')


def java_project_detected(c):
    """True when the java collector's project sub-collector found a pom.xml, build.gradle or
    build.gradle.kts at the component root."""
    project = c.get_node(".lang.java.project_exists")
    return project.exists() and bool(project.get_value())


def check_min_java_version_cicd(min_version=None, node=None, require_version=None):
    """Check that every Java version recorded in CI meets the minimum."""
    if min_version is None:
        min_version = variable_or_default("min_java_version_cicd", "17")
    if require_version is None:
        require_version = variable_or_default("require_java_version_cicd", "false")

    c = Check("min-java-version-cicd", "Ensures CI/CD Java version meets minimum", node=node)
    with c:
        cmds_node = c.get_node(".lang.java.cicd.cmds")
        # exists() keeps the check pending until collection finishes.
        cmds = cmds_node.get_value() if cmds_node.exists() else None
        if not cmds:
            try:
                required = parse_require(require_version)
            except ValueError as e:
                c.fail(f"require_java_version_cicd {e}")
                return c
            if not required:
                c.skip("No java or javac commands recorded in CI")
            if not java_project_detected(c):
                c.skip("No Java project detected and no java or javac commands recorded in CI")
            # Pending until collection finishes, then fails. Asserting on the first
            # entry also covers an empty list recorded before CI is done.
            c.assert_exists(".lang.java.cicd.cmds[0]", NO_EVIDENCE)
            return c

        try:
            minimum = parse_java_minimum(min_version)
        except ValueError as e:
            c.fail(f"min_java_version_cicd {e}")
            return c

        report_ci_versions(c, cmds, minimum, f"CI ran Java that does not meet {minimum.describe()}")
    return c


if __name__ == "__main__":
    check_min_java_version_cicd()
