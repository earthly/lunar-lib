from lunar_policy import Check


def check_test_directory_exists(node=None):
    """Check that the project has a `test/` directory with ExUnit tests."""
    c = Check(
        "test-directory-exists",
        "Ensures the project has a test/ directory",
        node=node,
    )
    with c:
        elixir = c.get_node(".lang.elixir")
        if not elixir.exists():
            c.skip("Not an Elixir project")

        test_dir_node = elixir.get_node(".test_directory_exists")
        has_test_dir = test_dir_node.get_value() if test_dir_node.exists() else False

        c.assert_true(
            has_test_dir,
            "test/ directory not found. Create a test/ directory and add ExUnit tests."
        )
    return c


if __name__ == "__main__":
    check_test_directory_exists()
