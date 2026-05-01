from lunar_policy import Check


def main(node=None):
    c = Check(
        "gitattributes-exists",
        "A `.gitattributes` file should be present in the repository",
        node=node,
    )
    with c:
        attrs = (
            c.get_node(".git.attributes").get_value_or_default(".", None)
        )
        if attrs is None:
            c.fail(
                "No `.gitattributes` file found. Add one — even a minimal "
                "`* text=auto` rule prevents cross-platform line-ending "
                "churn that bloats diffs and breaks CI."
            )
    return c


if __name__ == "__main__":
    main()
