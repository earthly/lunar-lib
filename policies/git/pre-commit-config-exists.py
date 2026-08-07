from lunar_policy import Check


def main(node=None):
    c = Check(
        "pre-commit-config-exists",
        "A pre-commit config file should exist in the repository",
        node=node,
    )
    with c:
        if not c.get_node(".git.pre_commit").exists():
            c.fail(
                "No `.pre-commit-config.yaml` found. Add a config (e.g. "
                "`pre-commit sample-config > .pre-commit-config.yaml`) to "
                "enforce lint/format/secret-scan hygiene before commits."
            )
    return c


if __name__ == "__main__":
    main()
