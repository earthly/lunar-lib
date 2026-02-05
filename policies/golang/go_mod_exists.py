from lunar_policy import Check


def check_go_mod_exists(node=None):
    """Check that go.mod file exists in a Go project."""
    c = Check("go-mod-exists", "Ensures go.mod exists", node=node)
    with c:
        go = c.get_node(".lang.go")
        if not go.exists():
            c.skip("Not a Go project")

        go_mod = go.get_node(".native.go_mod.exists")
        if not go_mod.exists():
            c.skip("Go module data not available - ensure golang collector has run")

        c.assert_true(
            go_mod.get_value(),
            "go.mod not found. Initialize with 'go mod init <module-path>'"
        )
    return c


if __name__ == "__main__":
    check_go_mod_exists()
