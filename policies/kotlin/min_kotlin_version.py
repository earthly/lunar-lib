"""Check that the Kotlin compiler version meets the minimum for its release line."""
from lunar_policy import Check, variable_or_default

from version_minimum import Runtime, check_build_version, parse_minimum

# A Kotlin release line is major.minor: 2.1, 2.2. Pre-releases look like 2.2.0-RC.
KOTLIN = Runtime("Kotlin", line_length=2, forms="2.1, 2.1.21 or 2.2.0-RC")


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

        try:
            minimum = parse_minimum(min_version, KOTLIN)
        except ValueError as e:
            c.fail(f"min_kotlin_version {e}")
            return c
        check_build_version(c, actual_version, minimum, " Update the Kotlin plugin version to {floor} or higher.")
    return c


if __name__ == "__main__":
    check_min_kotlin_version()
