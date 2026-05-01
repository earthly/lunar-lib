from lunar_policy import Check


def main(node=None):
    c = Check(
        "pre-commit-config-exists",
        "A pre-commit config file should exist in the repository",
        node=node,
    )
    with c:
        pre_commit = (
            c.get_node(".git.pre_commit").get_value_or_default(".", None)
        )
        if pre_commit is None:
            c.fail(
                "No `.pre-commit-config.yaml` found. Add a config (e.g. "
                "`pre-commit sample-config > .pre-commit-config.yaml`) to "
                "enforce lint/format/secret-scan hygiene before commits."
            )
    return c


if __name__ == "__main__":
    main()
