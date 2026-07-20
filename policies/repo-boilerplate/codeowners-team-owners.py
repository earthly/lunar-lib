from lunar_policy import Check


def main(node=None):
    c = Check(
        "codeowners-team-owners",
        "CODEOWNERS should include team-based owners",
        node=node,
    )
    with c:
        exists = c.get_node(".ownership.codeowners.exists")
        if not (exists.exists() and bool(exists.get_value())):
            c.skip("No CODEOWNERS file found (codeowners-exists covers this case)")
        else:
            team_owners = c.get_value(".ownership.codeowners.team_owners")
            c.assert_true(
                len(team_owners) > 0,
                "CODEOWNERS has no team-based owners (@org/team). "
                "Use team owners instead of only individuals for better ownership continuity.",
            )
    return c


if __name__ == "__main__":
    main()
