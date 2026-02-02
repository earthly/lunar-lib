from lunar_policy import Check


def check_go_mod_exists(node=None):
    """Check that go.mod file exists in a Go project."""
    c = Check("go-mod-exists", "Ensures go.mod exists", node=node)
    with c:
        # Skip if not a Go project
        if not c.get_node(".lang.go").exists():
            c.skip("Not a Go project")

        # Skip if native data not available (collector may not have run)
        if not c.get_node(".lang.go.native.go_mod.exists").exists():
            c.skip("Go module data not available - ensure golang collector has run")

        c.assert_true(
            c.get_value(".lang.go.native.go_mod.exists"),
            "go.mod not found. Initialize with 'go mod init <module-path>'"
        )
    return c


if __name__ == "__main__":
    check_go_mod_exists()
