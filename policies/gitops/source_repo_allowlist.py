from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check(
        "source-repo-allowlist",
        "Application manifest sources should be within the allowed repositories",
        node=node,
    )
    with c:
        if c.get_node(".cd.gitops").get_value_or_default(".", None) is None:
            c.skip("No GitOps (.cd.gitops) data — vendor not in use")

        allowed_str = variable_or_default("allowed_source_repos", "")
        allowed = [r.strip() for r in allowed_str.split(",") if r.strip()]
        if not allowed:
            raise ValueError(
                "Policy misconfiguration: 'allowed_source_repos' is empty. An "
                "allow-list must contain at least one entry. Configure allowed "
                "source repos or exclude the source-repo-allowlist check."
            )

        apps = c.get_node(".cd.gitops.applications")
        if apps.exists():
            for app in apps:
                name = app.get_value_or_default(".name", "<unknown>")
                path = app.get_value_or_default(".path", "<unknown>")
                repo = app.get_value_or_default(".source_ref.repoURL", None)
                if repo is None:
                    continue
                c.assert_true(
                    repo in allowed,
                    f"{path}: Application '{name}' source repo '{repo}' is not in "
                    f"the allow-list",
                )
    return c


if __name__ == "__main__":
    main()
