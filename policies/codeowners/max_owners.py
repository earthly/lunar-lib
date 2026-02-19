from lunar_policy import Check, variable_or_default


def main(node=None, max_owners_override=None):
    c = Check(
        "max-owners",
        "CODEOWNERS rules should not have too many owners",
        node=node,
    )
    with c:
        if not c.get_value(".ownership.codeowners.exists"):
            c.fail("No CODEOWNERS file found")
            return c

        max_owners = (
            max_owners_override
            if max_owners_override is not None
            else variable_or_default("max_owners_per_rule", "10")
        )
        try:
            max_owners = int(max_owners)
        except (ValueError, TypeError):
            raise ValueError(
                f"Policy misconfiguration: max_owners_per_rule must be a number, got: {max_owners}"
            )

        for rule in c.get_node(".ownership.codeowners.rules"):
            pattern = rule.get_value(".pattern")
            owner_count = rule.get_value(".owner_count")
            c.assert_less_or_equal(
                owner_count,
                max_owners,
                f"Rule '{pattern}' has {owner_count} owners, maximum is {max_owners}. "
                f"Too many owners often means nobody truly owns the code.",
            )
    return c


if __name__ == "__main__":
    main()
