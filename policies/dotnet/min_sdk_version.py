from lunar_policy import Check, variable_or_default


def _parse_version(v):
    """Parse dotted version string into a tuple of ints."""
    parts = str(v).split(".")
    return tuple(int(p) for p in parts)


def _compare_versions(actual_str, min_str):
    """Compare versions with zero-padding for unequal lengths.

    Returns True if actual >= minimum.
    """
    actual = _parse_version(actual_str)
    minimum = _parse_version(min_str)
    max_len = max(len(actual), len(minimum))
    actual_padded = actual + (0,) * (max_len - len(actual))
    min_padded = minimum + (0,) * (max_len - len(minimum))
    return actual_padded >= min_padded


def check_min_sdk_version(min_version=None, node=None):
    """Check that .NET SDK version meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_sdk_version", "8.0")

    c = Check("min-sdk-version", "Ensures .NET SDK version meets minimum", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        version_node = dotnet.get_node(".sdk_version")
        if not version_node.exists():
            c.skip("SDK version not detected (no global.json found)")

        actual_version = version_node.get_value()
        if not actual_version:
            c.skip("SDK version is empty")

        try:
            if not _compare_versions(actual_version, min_version):
                c.fail(
                    f".NET SDK version {actual_version} is below minimum {min_version}. "
                    f"Update global.json to specify SDK version {min_version} or higher."
                )
        except (ValueError, TypeError):
            c.fail(f"Could not parse SDK version: {actual_version}")
    return c


if __name__ == "__main__":
    check_min_sdk_version()
