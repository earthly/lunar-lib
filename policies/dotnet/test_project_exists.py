from lunar_policy import Check


def check_test_project_exists(node=None):
    """Check that at least one test project exists."""
    c = Check("test-project-exists", "Ensures test project exists", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        test_projects = dotnet.get_node(".test_projects")

        # If test_projects node doesn't exist or is empty, no test projects found
        if not test_projects.exists():
            c.info(
                "No test projects detected.\n\n"
                "Consider adding test projects:\n"
                "  dotnet new xunit -n MyProject.Tests\n"
                "  dotnet new nunit -n MyProject.Tests\n"
                "  dotnet new mstest -n MyProject.Tests\n\n"
                "Then add project reference:\n"
                "  dotnet add MyProject.Tests reference MyProject.csproj"
            )
            return c

        tests = test_projects.get_value()
        if not tests or len(tests) == 0:
            c.info(
                "No test projects detected.\n\n"
                "Consider adding test projects:\n"
                "  dotnet new xunit -n MyProject.Tests\n"
                "  dotnet new nunit -n MyProject.Tests\n"
                "  dotnet new mstest -n MyProject.Tests\n\n"
                "Then add project reference:\n"
                "  dotnet add MyProject.Tests reference MyProject.csproj"
            )
        else:
            test_frameworks = []
            for test in tests:
                if isinstance(test, dict):
                    framework = test.get("test_framework", "unknown")
                    test_frameworks.append(framework)

            framework_counts = {}
            for fw in test_frameworks:
                framework_counts[fw] = framework_counts.get(fw, 0) + 1

            framework_summary = ", ".join(f"{count} {fw}" for fw, count in framework_counts.items())
            c.pass_check(f"Found {len(tests)} test project(s): {framework_summary}")

    return c


if __name__ == "__main__":
    check_test_project_exists()