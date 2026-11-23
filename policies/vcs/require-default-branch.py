from lunar_policy import Check, variable_or_default

from settings_hint import REPOSITORY, with_hint


def main(node=None):
    c = Check("require-default-branch", "Default branch should match required name", node=node)
    with c:
        if not c.get_node(".vcs").exists():
            c.fail("VCS data not found. Ensure a VCS collector is configured and has run.")
            return c

        required_default_branch = variable_or_default("required_default_branch", "main")
        default_branch = c.get_value(".vcs.default_branch")

        c.assert_equals(default_branch, required_default_branch, with_hint(
            c, f"Default branch is '{default_branch}', but policy requires '{required_default_branch}'",
            REPOSITORY))
    return c


if __name__ == "__main__":
    main()
