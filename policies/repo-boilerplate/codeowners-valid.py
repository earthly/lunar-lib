from lunar_policy import Check


def main(node=None):
    c = Check(
        "codeowners-valid",
        "CODEOWNERS file should have valid syntax",
        node=node,
    )
    with c:
        exists = c.get_node(".ownership.codeowners.exists")
        if not (exists.exists() and bool(exists.get_value())):
            c.skip("No CODEOWNERS file found (codeowners-exists covers this case)")
        else:
            valid = c.get_value(".ownership.codeowners.valid")
            if not valid:
                errors = c.get_value_or_default(".ownership.codeowners.errors", [])
                for err in errors:
                    line = err.get("line", "?")
                    message = err.get("message", "Unknown error")
                    c.fail(f"Line {line}: {message}")
    return c


if __name__ == "__main__":
    main()
