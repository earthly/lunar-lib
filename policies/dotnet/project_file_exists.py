from lunar_policy import Check


def check_project_file_exists(node=None):
    """Check that at least one .NET project file exists."""
    c = Check("project-file-exists", "Ensures .NET project file exists", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        pf_node = dotnet.get_node(".project_files")
        if not pf_node.exists():
            c.skip("Project file data not available")

        project_files = pf_node.get_value()

        c.assert_true(
            len(project_files) > 0,
            "No .NET project files found. Create a .csproj, .fsproj, or .vbproj file "
            "using 'dotnet new console', 'dotnet new classlib', or 'dotnet new web'."
        )
    return c


if __name__ == "__main__":
    check_project_file_exists()
