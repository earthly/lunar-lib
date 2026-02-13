from lunar_policy import Check


def main(node=None):
    c = Check("catchall", "CODEOWNERS should have a default catch-all rule", node=node)
    with c:
        c.assert_true(c.get_value(".ownership.codeowners.exists"),
            "No CODEOWNERS file found")

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
