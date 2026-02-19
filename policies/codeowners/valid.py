from lunar_policy import Check


def main(node=None):
    c = Check("valid", "CODEOWNERS file should have valid syntax", node=node)
    with c:
        if not c.get_value(".ownership.codeowners.exists"):
            c.fail("No CODEOWNERS file found")
            return c

        valid = c.get_value(".ownership.codeowners.valid")
        if valid:
            return c

        errors = c.get_value_or_default(".ownership.codeowners.errors", [])
        for err in errors:
            line = err.get("line", "?")
            message = err.get("message", "Unknown error")
            c.fail(f"Line {line}: {message}")
    return c


if __name__ == "__main__":
    main()
