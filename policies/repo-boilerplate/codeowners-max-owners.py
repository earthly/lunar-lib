from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check(
        "codeowners-max-owners",
        "CODEOWNERS rules should not have too many owners",
        node=node,
    )
    with c:
        exists = c.get_node(".ownership.codeowners.exists")
        if not (exists.exists() and bool(exists.get_value())):
            c.skip("No CODEOWNERS file found (codeowners-exists covers this case)")
        else:
            max_owners = int(variable_or_default("max_owners_per_rule", "10"))

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
