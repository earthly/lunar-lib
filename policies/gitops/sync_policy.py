from lunar_policy import Check


def main(node=None):
    c = Check(
        "sync-policy",
        "Applications should use an automated sync policy with prune and self-heal",
        node=node,
    )
    with c:
        if c.get_node(".cd.gitops").get_value_or_default(".", None) is None:
            c.skip("No GitOps (.cd.gitops) data — vendor not in use")

        apps = c.get_node(".cd.gitops.applications")
        if apps.exists():
            for app in apps:
                name = app.get_value_or_default(".name", "<unknown>")
                path = app.get_value_or_default(".path", "<unknown>")
                automated = app.get_value_or_default(".sync_policy.automated", False)
                prune = app.get_value_or_default(".sync_policy.prune", False)
                self_heal = app.get_value_or_default(".sync_policy.self_heal", False)
                c.assert_true(
                    bool(automated) and bool(prune) and bool(self_heal),
                    f"{path}: Application '{name}' should use an automated sync policy "
                    f"with prune and self-heal",
                )
    return c


if __name__ == "__main__":
    main()
