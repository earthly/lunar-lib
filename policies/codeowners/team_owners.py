from lunar_policy import Check


def main(node=None):
    c = Check(
        "team-owners",
        "CODEOWNERS should include team-based owners",
        node=node,
    )
    with c:
        codeowners = c.get_node(".ownership.codeowners")
        if not codeowners.exists():
            c.skip("No codeowners data collected")
            return c

        if not codeowners.get_value(".exists"):
            c.fail("No CODEOWNERS file found")
            return c

        team_owners = codeowners.get_value(".team_owners")
        c.assert_true(
            len(team_owners) > 0,
            "CODEOWNERS has no team-based owners (@org/team). "
            "Use team owners instead of only individuals for better ownership continuity.",
        )
    return c


if __name__ == "__main__":
    main()
