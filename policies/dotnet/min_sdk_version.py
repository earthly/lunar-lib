"""Check that the global.json .NET SDK version meets the minimum for its feature band."""
from lunar_policy import Check, variable_or_default

from version_minimum import Runtime, check_build_version, parse_minimum

# Microsoft patches each SDK feature band separately (8.0.1xx, 8.0.4xx), so a
# release line is major.minor plus the band: 8.0.404 is on 8.0.4xx.
DOTNET = Runtime(
    ".NET SDK",
    line_length=3,
    forms="8.0, 8.0.404 or 9.0.100-rc.2.24474.11",
    feature_bands=True,
)


def check_min_sdk_version(min_version=None, node=None):
    """Check that .NET SDK version meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_sdk_version", "8.0")

    c = Check("min-sdk-version", "Ensures .NET SDK version meets minimum", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")
        project_exists_node = dotnet.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No .NET project detected in this component")

        sdk_version_node = dotnet.get_node(".sdk_version")
        if not sdk_version_node.exists():
            c.skip(".NET SDK version not detected in global.json")

        try:
            minimum = parse_minimum(min_version, DOTNET)
        except ValueError as e:
            c.fail(f"min_sdk_version {e}")
            return c
        check_build_version(
            c,
            sdk_version_node.get_value(),
            minimum,
            " Update global.json to specify SDK version {floor} or higher.",
        )
    return c


if __name__ == "__main__":
    check_min_sdk_version()
