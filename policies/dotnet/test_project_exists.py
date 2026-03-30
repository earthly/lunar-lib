from lunar_policy import Check


def check_test_project_exists(node=None):
    """Check that at least one test project exists."""
    c = Check("test-project-exists", "Ensures test project exists", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        tp_node = dotnet.get_node(".test_projects")
        if not tp_node.exists():
            c.skip("Test project data not available")

        test_projects = tp_node.get_value()

        c.assert_true(
            len(test_projects) > 0,
            "No test projects detected. Add a test project with "
            "'dotnet new xunit -n MyProject.Tests' and reference your main project."
        )
    return c


if __name__ == "__main__":
    check_test_project_exists()
