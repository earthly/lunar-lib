from lunar_policy import Check


def check_target_framework_set(node=None):
    """Check that all project files have a target framework specified."""
    c = Check("target-framework-set", "Ensures target framework is specified", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        pf_node = dotnet.get_node(".project_files")
        if not pf_node.exists():
            c.skip("Project file data not available")

        project_files = pf_node.get_value()
        if not project_files:
            c.skip("No project files to check")

        missing = []
        for pf in project_files:
            tf = pf.get("target_framework", "")
            if not tf:
                missing.append(pf.get("path", "unknown"))

        if missing:
            c.fail(
                f"{len(missing)} of {len(project_files)} project(s) missing target framework: "
                + ", ".join(missing)
                + ". Add <TargetFramework>net8.0</TargetFramework> to each project file."
            )
    return c


if __name__ == "__main__":
    check_target_framework_set()
