from lunar_policy import Check


def check_project_file_exists(node=None):
    """Check that at least one .NET project file exists."""
    c = Check("project-file-exists", "Ensures .NET project file exists", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        project_files_node = dotnet.get_node(".project_files")
        if not project_files_node.exists():
            c.fail("No .NET project files found. Create a .csproj, .fsproj, or .vbproj file.")

        project_files = project_files_node.get_value()
        if not project_files:
            c.fail("No .NET project files found. Create a .csproj, .fsproj, or .vbproj file.")

    return c


if __name__ == "__main__":
    check_project_file_exists()