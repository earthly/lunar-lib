from lunar_policy import Check


def main(node=None):
    c = Check(
        "codeowners-exists",
        "Repository should have a CODEOWNERS file",
        node=node,
    )
    with c:
        exists = c.get_node(".ownership.codeowners.exists")
        c.assert_true(
            exists.exists() and bool(exists.get_value()),
            "No CODEOWNERS file found. Add a CODEOWNERS file to the repository "
            "root, .github/, or docs/ directory.",
        )
    return c


if __name__ == "__main__":
    main()
