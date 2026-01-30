from lunar_policy import Check

with Check("go-mod-exists", "Ensures go.mod exists") as c:
    # Skip if not a Go project
    if not c.exists(".lang.go"):
        c.skip("Not a Go project")

    c.assert_true(
        c.get_value(".lang.go.native.go_mod.exists"),
        "go.mod not found. Initialize with 'go mod init <module-path>'"
    )
