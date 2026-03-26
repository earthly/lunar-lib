from lunar_policy import Check


def check_project_file_exists(node=None):
    """Check that at least one .NET project file exists."""
    c = Check("project-file-exists", "Ensures .NET project file exists", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        project_files = dotnet.get_node(".project_files")
        if not project_files.exists():
            c.fail(
                "No .NET project files found. Create a .csproj, .fsproj, or .vbproj file.\n"
                "For C#: dotnet new console/classlib/web\n"
                "For F#: dotnet new console -lang F#"
            )

        # Check if project_files array is empty
        files = project_files.get_value()
        if not files or len(files) == 0:
            c.fail(
                "No .NET project files found. Create a .csproj, .fsproj, or .vbproj file.\n"
                "For C#: dotnet new console/classlib/web\n"
                "For F#: dotnet new console -lang F#"
            )

        c.pass_check(f"Found {len(files)} .NET project file(s)")

    return c


if __name__ == "__main__":
    check_project_file_exists()