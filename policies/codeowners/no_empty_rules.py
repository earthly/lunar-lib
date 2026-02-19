from lunar_policy import Check


def main(node=None):
    c = Check(
        "no-empty-rules",
        "CODEOWNERS rules should not un-assign ownership",
        node=node,
    )
    with c:
        if not c.get_value(".ownership.codeowners.exists"):
            c.fail("No CODEOWNERS file found")
            return c

        for rule in c.get_node(".ownership.codeowners.rules"):
            pattern = rule.get_value(".pattern")
            owner_count = rule.get_value(".owner_count")
            c.assert_true(
                owner_count > 0,
                f"Rule '{pattern}' has no owners, which un-assigns ownership for matching files.",
            )
    return c


if __name__ == "__main__":
    main()
