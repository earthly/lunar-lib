from lunar_policy import Check

with Check("codeowners-catchall", "CODEOWNERS should have a default catch-all rule") as c:
    if not c.get_value(".ownership.codeowners.exists"):
        c.fail("No CODEOWNERS file found")
    else:
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
