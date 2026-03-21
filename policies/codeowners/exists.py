from lunar_policy import Check


def main(node=None):
    c = Check("exists", "Repository should have a CODEOWNERS file", node=node)
    with c:
        codeowners = c.get_node(".ownership.codeowners")
        if not codeowners.exists():
            c.skip("No codeowners data collected")
            return c

        c.assert_true(
            codeowners.get_value(".exists"),
            "No CODEOWNERS file found. Add a CODEOWNERS file to the repository root, .github/, or docs/ directory.",
        )
    return c


if __name__ == "__main__":
    main()
