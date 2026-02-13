from lunar_policy import Check, variable_or_default


def main(node=None, min_owners_override=None):
    c = Check(
        "min-owners",
        "Each CODEOWNERS rule should have a minimum number of owners",
        node=node,
    )
    with c:
        c.assert_true(c.get_value(".ownership.codeowners.exists"),
            "No CODEOWNERS file found")

        min_owners = (
            min_owners_override
            if min_owners_override is not None
            else variable_or_default("min_owners_per_rule", "2")
        )
        try:
            min_owners = int(min_owners)
        except (ValueError, TypeError):
            raise ValueError(
                f"Policy misconfiguration: min_owners_per_rule must be a number, got: {min_owners}"
            )

        for rule in c.get_node(".ownership.codeowners.rules"):
            pattern = rule.get_value(".pattern")
            owner_count = rule.get_value(".owner_count")
            # Skip rules that intentionally un-assign ownership (0 owners)
            # — those are caught by the no-empty-rules check
            if owner_count == 0:
                continue
            c.assert_greater_or_equal(
                owner_count,
                min_owners,
                f"Rule '{pattern}' has {owner_count} owner(s), minimum is {min_owners}",
            )
    return c


if __name__ == "__main__":
    main()
