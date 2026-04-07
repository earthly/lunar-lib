import re
from lunar_policy import Check, variable_or_default


def _parse_version(version_str):
    """Parse a version string into a comparable tuple."""
    m = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(version_str).strip())
    if m:
        major = int(m.group(1))
        minor = int(m.group(2)) if m.group(2) else 0
        patch = int(m.group(3)) if m.group(3) else 0
        return (major, minor, patch)
    return None


def min_cmake_version_cicd(min_version=None, node=None):
    """Ensures CMake version in CI meets minimum."""
    if min_version is None:
        min_version = variable_or_default("min_cmake_version", "3.20.0")

    c = Check("min-cmake-version-cicd", "Ensures CI CMake version meets minimum", node=node)
    with c:
        cpp = c.get_node(".lang.cpp")
        if not cpp.exists():
            c.skip("Not a C/C++ project")

        cicd_node = cpp.get_node(".cicd")
        if not cicd_node.exists():
            c.skip("No CI/CD data available - ensure cpp collector cicd hook has run")

        cmds_node = cicd_node.get_node(".cmds")
        if not cmds_node.exists():
            c.skip("No CMake commands recorded in CI")

        cmds = cmds_node.get_value()
        if not cmds:
            c.skip("No CMake commands recorded in CI")

        minimum = _parse_version(min_version)
        if minimum is None:
            c.fail(f"Invalid minimum version format: '{min_version}'")

        # Filter for cmake commands only
        cmake_cmds = [
            ci for ci in cmds
            if ci.get("cmd", "").strip().startswith("cmake")
        ]
        if not cmake_cmds:
            c.skip("No CMake commands found in CI data")

        violations = []
        for cmd_info in cmake_cmds:
            cmd_name = cmd_info.get("cmd", "unknown")
            version = cmd_info.get("version")
            if not version:
                continue
            actual = _parse_version(version)
            if actual is None:
                violations.append(f"'{cmd_name}' has unparseable version '{version}'")
                continue
            if actual < minimum:
                violations.append(f"'{cmd_name}' used version {version}")

        if violations:
            c.fail(
                f"CMake version(s) below minimum {min_version}:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )

    return c


if __name__ == "__main__":
    min_cmake_version_cicd()
