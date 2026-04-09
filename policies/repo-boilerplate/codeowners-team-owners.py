from lunar_policy import Check

with Check("codeowners-team-owners", "CODEOWNERS should include team-based owners") as c:
    if not c.get_value(".ownership.codeowners.exists"):
        c.fail("No CODEOWNERS file found")
    else:
        team_owners = c.get_value(".ownership.codeowners.team_owners")
        c.assert_true(
            len(team_owners) > 0,
            "CODEOWNERS has no team-based owners (@org/team). "
            "Use team owners instead of only individuals for better ownership continuity.",
        )
