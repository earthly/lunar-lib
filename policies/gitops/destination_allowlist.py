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
        # Each entry is "namespace" (allowed on any cluster) or
        # "cluster/namespace" (pinned to one cluster). The cluster segment is
        # matched against the ArgoCD destination's registered `name` OR its
        # `server` URL — whichever the Application specifies (the two are
        # mutually exclusive in argo). Split on the LAST slash so a server URL
        # ("https://host/namespace") parses cleanly.
        rules = []  # (cluster_or_None, namespace)
        for e in allowed:
            if "/" in e:
                cluster, ns = e.rsplit("/", 1)
                rules.append((cluster, ns))
            else:
                rules.append((None, e))

        apps = c.get_node(".cd.gitops.applications")
        if apps.exists():
            for app in apps:
                name = app.get_value_or_default(".name", "<unknown>")
                path = app.get_value_or_default(".path", "<unknown>")
                ns = app.get_value_or_default(".destination.namespace", None)
                if ns is None:
                    continue
                dest_name = app.get_value_or_default(".destination.name", None)
                dest_server = app.get_value_or_default(".destination.server", None)
                allowed_here = any(
                    ns == r_ns
                    and (
                        r_cluster is None
                        or r_cluster == dest_name
                        or r_cluster == dest_server
                    )
                    for r_cluster, r_ns in rules
                )
                where = dest_name or dest_server or "<any-cluster>"
                c.assert_true(
                    allowed_here,
                    f"{path}: Application '{name}' destination '{where}/{ns}' is "
                    f"not in the allow-list",
                )
    return c


if __name__ == "__main__":
    main()
