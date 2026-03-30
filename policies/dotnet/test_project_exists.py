from lunar_policy import Check


def check_test_project_exists(node=None):
    """Check that at least one test project exists."""
    c = Check("test-project-exists", "Ensures at least one test project exists", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        test_projects_node = dotnet.get_node(".test_projects")
        if not test_projects_node.exists():
            c.fail("No test projects detected. Consider adding test projects with 'dotnet new xunit'.")

        test_projects = test_projects_node.get_value()
        if not test_projects:
            c.fail("No test projects detected. Consider adding test projects with 'dotnet new xunit'.")

    return c


if __name__ == "__main__":
    check_test_project_exists()