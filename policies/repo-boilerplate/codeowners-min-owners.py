from lunar_policy import Check, variable_or_default

with Check("codeowners-min-owners", "Each CODEOWNERS rule should have a minimum number of owners") as c:
    if not c.get_value(".ownership.codeowners.exists"):
        c.fail("No CODEOWNERS file found")
    else:
        min_owners = int(variable_or_default("min_owners_per_rule", "2"))

        for rule in c.get_node(".ownership.codeowners.rules"):
            pattern = rule.get_value(".pattern")
            owner_count = rule.get_value(".owner_count")
            # Skip rules that intentionally un-assign ownership (0 owners)
            if owner_count == 0:
                continue
            c.assert_greater_or_equal(
                owner_count,
                min_owners,
                f"Rule '{pattern}' has {owner_count} owner(s), minimum is {min_owners}",
            )
