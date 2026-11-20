"""Check that the .NET SDK used in CI/CD meets the minimum for its feature band."""
from lunar_policy import Check, variable_or_default

from min_sdk_version import DOTNET
from version_minimum import parse_minimum, report_ci_versions


def check_min_sdk_version_cicd(min_version=None, node=None):
    """Check that .NET SDK version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_sdk_version_cicd", "8.0")

    c = Check("min-sdk-version-cicd", "Ensures CI/CD .NET SDK version meets minimum", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        cmds_node = dotnet.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No CI/CD commands recorded")

        cmds = cmds_node.get_value()
        if not cmds:
            c.skip("No CI/CD commands recorded")

        try:
            minimum = parse_minimum(min_version, DOTNET)
        except ValueError as e:
            c.fail(f"min_sdk_version_cicd {e}")
            return c
        # dotnet also runs apps, which may have no SDK to report a version.
        report_ci_versions(c, cmds, minimum, skip_unrecorded=True)
    return c


if __name__ == "__main__":
    check_min_sdk_version_cicd()
