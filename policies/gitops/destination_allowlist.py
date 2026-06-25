from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check(
        "destination-allowlist",
        "Application destinations should be within the allowed namespaces/clusters",
        node=node,
    )
    with c:
        if c.get_node(".cd.gitops").get_value_or_default(".", None) is None:
            c.skip("No GitOps (.cd.gitops) data — vendor not in use")

        allowed_str = variable_or_default("allowed_destinations", "")
        allowed = [d.strip() for d in allowed_str.split(",") if d.strip()]
        if not allowed:
            raise ValueError(
                "Policy misconfiguration: 'allowed_destinations' is empty. An "
                "allow-list must contain at least one entry. Configure allowed "
                "destinations or exclude the destination-allowlist check."
            )
        # An entry may be "namespace" or "cluster/namespace" — accept the
        # trailing namespace segment for matching.
        allowed_ns = {e.split("/")[-1] for e in allowed}

        apps = c.get_node(".cd.gitops.applications")
        if apps.exists():
            for app in apps:
                name = app.get_value_or_default(".name", "<unknown>")
                path = app.get_value_or_default(".path", "<unknown>")
                ns = app.get_value_or_default(".destination.namespace", None)
                if ns is None:
                    continue
                c.assert_true(
                    ns in allowed_ns or ns in allowed,
                    f"{path}: Application '{name}' destination namespace '{ns}' is "
                    f"not in the allow-list",
                )
    return c


if __name__ == "__main__":
    main()
