from lunar_policy import Check


def check_target_framework_set(node=None):
    """Check that all project files have target frameworks specified."""
    c = Check("target-framework-set", "Ensures target framework is specified", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        project_files_node = dotnet.get_node(".project_files")
        if not project_files_node.exists():
            c.skip("No project files detected")

        project_files = project_files_node.get_value()
        if not project_files:
            c.skip("No project files detected")

        missing_framework = []
        for proj in project_files:
            proj_path = proj.get("path", "unknown")
            if "target_framework" not in proj or not proj["target_framework"]:
                missing_framework.append(proj_path)

        if missing_framework:
            count = len(missing_framework)
            total = len(project_files)
            c.fail(
                f"{count} of {total} project(s) missing target framework: "
                f"{', '.join(missing_framework)}. "
                f"Add <TargetFramework>net8.0</TargetFramework> to project files."
            )

    return c


if __name__ == "__main__":
    check_target_framework_set()