"""Check that the go.mod Go version meets the minimum for its release line."""
from lunar_policy import Check, variable_or_default

from version_minimum import Runtime, check_build_version, parse_minimum

# A Go release line is major.minor: 1.22, 1.23. Pre-releases look like 1.23rc1.
GO = Runtime("Go", line_length=2, forms="1.22, 1.22.7 or 1.23rc1")


def check_min_go_version(min_version=None, node=None):
    """Check that Go version meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_go_version", "1.21")

    c = Check("min-go-version", "Ensures Go version meets minimum", node=node)
    with c:
        go = c.get_node(".lang.go")
        if not go.exists():
            c.skip("Not a Go project")
        project_exists_node = go.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Go project detected in this component")

        version_node = go.get_node(".version")
        if not version_node.exists():
            c.skip("Go version not detected")

        try:
            minimum = parse_minimum(min_version, GO)
        except ValueError as e:
            c.fail(f"min_go_version {e}")
            return c
        # go.mod's go line is the oldest Go the module builds with (Go 1.21+
        # enforces it), so "go 1.22" is held to the 1.22 minimum like 1.22.0.
        check_build_version(c, version_node.get_value(), minimum, " Update go.mod to require Go {floor} or higher.")
    return c


if __name__ == "__main__":
    check_min_go_version()
