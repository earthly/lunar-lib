from lunar_policy import Check

with Check("codeowners-valid", "CODEOWNERS file should have valid syntax") as c:
    if not c.get_value(".ownership.codeowners.exists"):
        c.fail("No CODEOWNERS file found")
    else:
        valid = c.get_value(".ownership.codeowners.valid")
        if not valid:
            errors = c.get_value_or_default(".ownership.codeowners.errors", [])
            for err in errors:
                line = err.get("line", "?")
                message = err.get("message", "Unknown error")
                c.fail(f"Line {line}: {message}")
