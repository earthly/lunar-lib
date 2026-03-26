from lunar_policy import Check


def check_target_framework_set(node=None):
    """Check that all .NET projects have target frameworks specified."""
    c = Check("target-framework-set", "Ensures target framework is specified", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        project_files = dotnet.get_node(".project_files")
        if not project_files.exists():
            c.skip(".NET project data not available - ensure dotnet collector has run")

        files = project_files.get_value()
        if not files:
            c.skip("No project files found")

        # Check each project file for target framework
        missing_frameworks = []
        total_projects = len(files)

        for project in files:
            if isinstance(project, dict):
                target_framework = project.get("target_framework")
                if not target_framework:
                    project_path = project.get("path", "unknown")
                    missing_frameworks.append(project_path)

        if missing_frameworks:
            project_list = "\n".join(f"  - {path}" for path in missing_frameworks)
            c.warn(
                f"{len(missing_frameworks)} of {total_projects} project(s) missing target framework:\n"
                f"{project_list}\n\n"
                f"Add <TargetFramework>net8.0</TargetFramework> (or appropriate version) to project files."
            )
        else:
            c.pass_check(f"All {total_projects} project(s) have target frameworks specified")

    return c


if __name__ == "__main__":
    check_target_framework_set()