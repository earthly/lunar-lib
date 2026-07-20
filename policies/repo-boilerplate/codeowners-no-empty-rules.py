from lunar_policy import Check


def main(node=None):
    c = Check(
        "codeowners-no-empty-rules",
        "CODEOWNERS rules should not un-assign ownership",
        node=node,
    )
    with c:
        exists = c.get_node(".ownership.codeowners.exists")
        if not (exists.exists() and bool(exists.get_value())):
            c.skip("No CODEOWNERS file found (codeowners-exists covers this case)")
        else:
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
