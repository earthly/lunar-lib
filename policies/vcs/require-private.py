from lunar_policy import Check

from settings_hint import REPOSITORY, with_hint


def main(node=None):
    c = Check("require-private", "Repository must be private", node=node)
    with c:
        if not c.get_node(".vcs").exists():
            c.fail("VCS data not found. Ensure a VCS collector is configured and has run.")
            return c

        visibility = c.get_value(".vcs.visibility")
        c.assert_equals(visibility, "private", with_hint(
            c, f"Repository visibility is '{visibility}', but policy requires 'private'",
            REPOSITORY))
    return c


if __name__ == "__main__":
    main()
