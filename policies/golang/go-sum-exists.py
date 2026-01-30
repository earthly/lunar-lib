from lunar_policy import Check

with Check("go-sum-exists", "Ensures go.sum exists") as c:
    # Skip if not a Go project
    if not c.exists(".lang.go"):
        c.skip("Not a Go project")

    c.assert_true(
        c.get_value(".lang.go.native.go_sum.exists"),
        "go.sum not found. Run 'go mod tidy' to generate checksums."
    )
