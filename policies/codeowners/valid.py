from lunar_policy import Check


def main(node=None):
    c = Check("valid", "CODEOWNERS file should have valid syntax", node=node)
    with c:
        codeowners = c.get_node(".ownership.codeowners")
        if not codeowners.exists():
            c.skip("No codeowners data collected")
            return c

        if not codeowners.get_value(".exists"):
            c.fail("No CODEOWNERS file found")
            return c

        valid = codeowners.get_value(".valid")
        if valid:
            return c

        errors = codeowners.get_value_or_default(".errors", [])
        for err in errors:
            line = err.get("line", "?")
            message = err.get("message", "Unknown error")
            c.fail(f"Line {line}: {message}")
    return c


if __name__ == "__main__":
    main()
