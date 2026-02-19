from lunar_policy import Check


def main(node=None):
    c = Check("catchall", "CODEOWNERS should have a default catch-all rule", node=node)
    with c:
        # Check if CODEOWNERS exists - return early if not
        # (get_value handles nodata properly -> PENDING if collector not done)
        if not c.get_value(".ownership.codeowners.exists"):
            c.fail("No CODEOWNERS file found")
            return c

        has_catchall = False
        for rule in c.get_node(".ownership.codeowners.rules"):
            if rule.get_value(".pattern") == "*":
                has_catchall = True
                break

        c.assert_true(
            has_catchall,
            "CODEOWNERS has no default catch-all rule (*). "
            "Add a '* @your-team' rule so every file has an owner.",
        )
    return c


if __name__ == "__main__":
    main()
