from lunar_policy import Check


def main(node=None):
    c = Check(
        "pre-commit-ci-skip-empty",
        "pre-commit `ci.skip` must be empty — no hooks silently disabled in pre-commit.ci",
        node=node,
    )
    with c:
        pre_commit = (
            c.get_node(".git.pre_commit").get_value_or_default(".", None)
        )
        if pre_commit is None:
            c.skip(
                "No pre-commit config found "
                "(pre-commit-config-exists covers this case)"
            )
            return c

        ci_skip = pre_commit.get("ci_skip") or []
        if ci_skip:
            count = len(ci_skip)
            ids = ", ".join(ci_skip)
            c.fail(
                f"`ci.skip` disables {count} hook(s) in pre-commit.ci: {ids}. "
                "Remove the entries or remove the hooks from the config "
                "entirely."
            )
    return c


if __name__ == "__main__":
    main()
