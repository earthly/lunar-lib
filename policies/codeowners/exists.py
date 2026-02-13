from lunar_policy import Check


def main(node=None):
    c = Check("exists", "Repository should have a CODEOWNERS file", node=node)
    with c:
        c.assert_exists(
            ".ownership.codeowners.rules",
            "No CODEOWNERS file found. Add a CODEOWNERS file to the repository root, .github/, or docs/ directory.",
        )
    return c


if __name__ == "__main__":
    main()
