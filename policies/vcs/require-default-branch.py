from lunar_policy import Check, variable_or_default


def main():
    with Check("require-default-branch", "Default branch should match required name") as c:
        vcs = c.get_node(".vcs")

        if not vcs.exists():
            c.skip("No VCS data collected")

        required_default_branch = variable_or_default("required_default_branch", "main")
        default_branch = vcs.get_value_or_default(".default_branch", None)

        if default_branch and default_branch != required_default_branch:
            c.fail(f"Default branch is '{default_branch}', but policy requires '{required_default_branch}'")


if __name__ == "__main__":
    main()
