from lunar_policy import Check


def main(node=None):
    c = Check("catchall", "CODEOWNERS should have a default catch-all rule", node=node)
    with c:
        codeowners = c.get_node(".ownership.codeowners")
        if not codeowners.exists():
            c.skip("No codeowners data collected")
            return c

        if not codeowners.get_value(".exists"):
            c.fail("No CODEOWNERS file found")
            return c

        has_catchall = False
        for rule in codeowners.get_node(".rules"):
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
