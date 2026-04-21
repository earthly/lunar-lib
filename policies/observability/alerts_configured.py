from lunar_policy import Check


def main(node=None):
    c = Check(
        "alerts-configured",
        "Service has alert rules configured",
        node=node,
    )
    with c:
        source = c.get_node(".observability.source")
        if not source.exists():
            c.skip("No observability source has written data for this component")

        alerts_configured_node = c.get_node(".observability.alerts.configured")
        c.assert_true(
            alerts_configured_node.exists() and bool(alerts_configured_node.get_value()),
            "Service has no alert rules configured. Add at least one alert "
            "rule scoped to the service's dashboard folder in Grafana (or "
            "the equivalent in your monitoring tool).",
        )
    return c


if __name__ == "__main__":
    main()
