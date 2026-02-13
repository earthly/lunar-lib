from lunar_policy import Check


def main(node=None):
    c = Check(
        "team-owners",
        "CODEOWNERS should include team-based owners",
        node=node,
    )
    with c:
        c.assert_exists(".ownership.codeowners.team_owners",
            "No CODEOWNERS file found. Ensure the codeowners collector is configured.")

        team_owners = c.get_value(".ownership.codeowners.team_owners")
        c.assert_true(
            len(team_owners) > 0,
            "CODEOWNERS has no team-based owners (@org/team). "
            "Use team owners instead of only individuals for better ownership continuity.",
        )
    return c


if __name__ == "__main__":
    main()
