from lunar_policy import Check, Path

with Check("codeowners", "CODEOWNERS Are Configured") as c:
    c.assert_false(Path(".repo.codeowners.missing"), "No CODEOWNERS file")
