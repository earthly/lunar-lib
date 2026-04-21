from lunar_policy import Check


def main(node=None):
    c = Check(
        "dashboard-exists",
        "Service has a linked monitoring dashboard",
        node=node,
    )
    with c:
        source = c.get_node(".observability.source")
        if not source.exists():
            c.skip("No observability source has written data for this component")

        dashboard_exists_node = c.get_node(".observability.dashboard.exists")
        c.assert_true(
            dashboard_exists_node.exists() and bool(dashboard_exists_node.get_value()),
            "Service has no linked monitoring dashboard. Register the "
            "dashboard UID via 'lunar catalog component --meta "
            "grafana/dashboard-uid <uid>' (Grafana) or the equivalent for "
            "your monitoring tool.",
        )
    return c


if __name__ == "__main__":
    main()
