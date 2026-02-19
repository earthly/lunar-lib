from lunar_policy import Check


def check_go_sum_exists(node=None):
    """Check that go.sum file exists in a Go project."""
    c = Check("go-sum-exists", "Ensures go.sum exists", node=node)
    with c:
        go = c.get_node(".lang.go")
        if not go.exists():
            c.skip("Not a Go project")

        go_sum = go.get_node(".go_sum_exists")
        if not go_sum.exists():
            c.skip("Go module data not available - ensure golang collector has run")

        c.assert_true(
            go_sum.get_value(),
            "go.sum not found. Run 'go mod tidy' to generate checksums."
        )
    return c


if __name__ == "__main__":
    check_go_sum_exists()
