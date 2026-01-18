from lunar_policy import Check, variable_or_default


def main():
    with Check("require-default-branch", "Default branch should match required name") as c:
        required_default_branch = variable_or_default("required_default_branch", "main")
        default_branch = c.get_value(".vcs.default_branch")

        if default_branch != required_default_branch:
            c.fail(f"Default branch is '{default_branch}', but policy requires '{required_default_branch}'")


if __name__ == "__main__":
    main()
