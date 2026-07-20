from lunar_policy import Check


def main(node=None):
    c = Check(
        "codeowners-no-individuals-only",
        "Each CODEOWNERS rule should include at least one team owner",
        node=node,
    )
    with c:
        exists = c.get_node(".ownership.codeowners.exists")
        if not (exists.exists() and bool(exists.get_value())):
            c.skip("No CODEOWNERS file found (codeowners-exists covers this case)")
        else:
            team_owners = set(c.get_value(".ownership.codeowners.team_owners"))

            for rule in c.get_node(".ownership.codeowners.rules"):
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
