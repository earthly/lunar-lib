from lunar_policy import Check


def check_test_module_exists(node=None):
    """Check that the project has a test source directory."""
    c = Check(
        "test-module-exists",
        "Ensures src/test/scala (or cross-version variant) exists",
        node=node,
    )
    with c:
        scala = c.get_node(".lang.scala")
        if not scala.exists():
            c.skip("Not a Scala project")

        test_node = scala.get_node(".test_directory_exists")
        has_tests = test_node.get_value() if test_node.exists() else False

        c.assert_true(
            has_tests,
            "src/test/scala not found. Add a test source directory and "
            "tests using ScalaTest, MUnit, or Specs2.",
        )
    return c


if __name__ == "__main__":
    check_test_module_exists()
