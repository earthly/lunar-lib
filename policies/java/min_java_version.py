import re
from lunar_policy import Check, variable_or_default


def _parse_java_major(version_str):
    """Extract major Java version from various formats.

    Handles: "17", "17.0.2", "1.8", "1.8.0_202"
    Java 8 and earlier use 1.x format (1.8 = Java 8).
    Java 9+ use the major number directly.
    """
    s = str(version_str).strip()
    m = re.match(r"^1\.(\d+)", s)
    if m:
        return int(m.group(1))  # 1.8 -> 8
    m = re.match(r"^(\d+)", s)
    if m:
        return int(m.group(1))  # 17.0.2 -> 17
    return None


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
        actual_major = _parse_java_major(actual_version)
        min_major = _parse_java_major(min_version)

        if actual_major is None:
            c.fail(f"Could not parse Java version: {actual_version}")
        elif min_major is None:
            c.fail(f"Could not parse minimum version: {min_version}")
        else:
            c.assert_true(
                actual_major >= min_major,
                f"Java version {actual_version} (major: {actual_major}) is below minimum {min_version}. "
                f"Update your build config to target Java {min_version} or higher."
            )
    return c


if __name__ == "__main__":
    check_min_java_version()
