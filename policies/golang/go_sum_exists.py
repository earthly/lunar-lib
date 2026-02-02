from lunar_policy import Check


def check_go_sum_exists(node=None):
    """Check that go.sum file exists in a Go project."""
    c = Check("go-sum-exists", "Ensures go.sum exists", node=node)
    with c:
        # Skip if not a Go project
        if not c.exists(".lang.go"):
            c.skip("Not a Go project")

        # Skip if native data not available (collector may not have run)
        if not c.exists(".lang.go.native.go_sum.exists"):
            c.skip("Go module data not available - ensure golang collector has run")

        c.assert_true(
            c.get_value(".lang.go.native.go_sum.exists"),
            "go.sum not found. Run 'go mod tidy' to generate checksums."
        )
    return c


if __name__ == "__main__":
    check_go_sum_exists()
