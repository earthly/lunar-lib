from lunar_policy import Check


def main(node=None):
    c = Check(
        "no-individuals-only",
        "Each CODEOWNERS rule should include at least one team owner",
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

        team_owners = set(codeowners.get_value(".team_owners"))

        for rule in codeowners.get_node(".rules"):
            owners = rule.get_value_or_default(".owners", [])
            if not owners:
                continue  # Empty rules handled by no-empty-rules check

            pattern = rule.get_value(".pattern")
            has_team = any(o in team_owners for o in owners)
            c.assert_true(
                has_team,
                f"Rule '{pattern}' has only individual owners: {', '.join(owners)}. "
                f"Add a team owner (@org/team) for continuity.",
            )
    return c


if __name__ == "__main__":
    main()
