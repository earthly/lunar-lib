from lunar_policy import Check


def main(node=None):
    """Requires mesh namespaces to enable sidecar injection; flags opt-outs."""
    c = Check("sidecar-injection", "Mesh namespaces should enable sidecar injection", node=node)
    with c:
        mesh = c.get_node(".mesh")
        if not mesh.exists():
            c.skip("No service-mesh configuration found in this repository")

        namespaces = c.get_node(".mesh.injection.namespaces")
        if namespaces.exists():
            for ns in namespaces:
                name = ns.get_value_or_default(".name", "<unknown>")
                enabled = ns.get_value_or_default(".enabled", False)
                c.assert_true(
                    enabled is True,
                    f"Namespace {name} carries Istio injection config but injection is not "
                    f"enabled — label it istio-injection=enabled or istio.io/rev=<rev>"
                )

        overrides = c.get_node(".mesh.injection.workload_overrides")
        if overrides.exists():
            for w in overrides:
                kind = w.get_value_or_default(".kind", "workload")
                name = w.get_value_or_default(".name", "<unknown>")
                namespace = w.get_value_or_default(".namespace", "default")
                inject = w.get_value_or_default(".inject", True)
                c.assert_true(
                    inject is not False,
                    f"{kind} {namespace}/{name} sets sidecar.istio.io/inject: \"false\" — "
                    f"it silently bypasses mesh mTLS, authorization, and telemetry"
                )

    return c


if __name__ == "__main__":
    main()
