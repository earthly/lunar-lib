from lunar_policy import Check

FLOATING_REFS = {"main", "master", "head", "develop", "trunk"}


def main(node=None):
    c = Check(
        "pre-commit-pinned-refs",
        "Every pre-commit repo entry must pin `rev` to an immutable ref",
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

        repos = pre_commit.get("repos") or []
        for repo in repos:
            repo_url = repo.get("repo") or "<unknown>"
            if repo_url == "meta":
                continue
            rev = (repo.get("rev") or "").strip()
            if not rev:
                c.fail(
                    f"Repo '{repo_url}' has no `rev` — pin to a tag or "
                    "commit SHA"
                )
                continue
            if rev.lower() in FLOATING_REFS:
                c.fail(
                    f"Repo '{repo_url}' uses floating ref '{rev}' — pin to "
                    "a tag or commit SHA"
                )
    return c


if __name__ == "__main__":
    main()
