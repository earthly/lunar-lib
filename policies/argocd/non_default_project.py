from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check(
        "non-default-project",
        "Applications should run under a scoped (non-default) AppProject",
        node=node,
    )
    with c:
        if c.get_node(".cd.gitops").get_value_or_default(".", None) is None:
            c.skip("No GitOps (.cd.gitops) data — vendor not in use")

        allowed_str = variable_or_default("allowed_projects", "")
        allowed = [p.strip() for p in allowed_str.split(",") if p.strip()]

        apps = c.get_node(".cd.gitops.applications")
        if apps.exists():
            for app in apps:
                name = app.get_value_or_default(".name", "<unknown>")
                path = app.get_value_or_default(".path", "<unknown>")
                project = app.get_value_or_default(".project", "default")
                c.assert_true(
                    project != "default",
                    f"{path}: Application '{name}' uses the 'default' AppProject; "
                    f"use a scoped project",
                )
                if allowed and project != "default":
                    c.assert_true(
                        project in allowed,
                        f"{path}: Application '{name}' project '{project}' is not "
                        f"in the allow-list",
                    )
    return c


if __name__ == "__main__":
    main()
