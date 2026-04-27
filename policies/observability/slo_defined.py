from lunar_policy import Check


def main(node=None):
    c = Check(
        "slo-defined",
        "Service has a Service Level Objective defined",
        node=node,
    )
    with c:
        source = c.get_node(".observability.source")
        if not source.exists():
            c.skip("No observability source has written data for this component")

        slo_defined_node = c.get_node(".observability.slo.defined")
        c.assert_true(
            slo_defined_node.exists() and bool(slo_defined_node.get_value()),
            "Service has no Service Level Objective defined. Define an SLO "
            "in your observability tool (e.g. Datadog Service Mgmt → SLOs) "
            "scoped to the service tag so reliability targets are explicit.",
        )
    return c


if __name__ == "__main__":
    main()
