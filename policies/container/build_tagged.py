"""Check that container builds use explicit image tags."""

from lunar_policy import Check


def main(node=None):
    c = Check(
        "build-tagged",
        "Container builds should use explicit image tags",
        node=node,
    )
    with c:
        builds = c.get_node(".containers.builds")
        if not builds.exists():
            c.skip("No container builds observed in CI for this component")
            return c

        for build in builds:
            cmd = build.get_value_or_default(".cmd", "<unknown>")
            has_tag = build.get_value_or_default(".has_tag", False)

            c.assert_true(
                has_tag,
                f"Build command missing -t/--tag flag: {cmd}"
            )
    return c


if __name__ == "__main__":
    main()
