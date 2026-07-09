from lunar_policy import Check


def main(node=None):
    """Advisory: flags EnvoyFilter usage (brittle low-level Envoy patching)."""
    c = Check("no-envoy-filter", "Mesh should avoid EnvoyFilter", node=node)
    with c:
        mesh = c.get_node(".mesh")
        if not mesh.exists():
            c.skip("No service-mesh configuration found in this repository")

        efs = c.get_node(".mesh.envoy_filters")
        if efs.exists():
            for ef in efs:
                name = ef.get_value_or_default(".name", "<unknown>")
                namespace = ef.get_value_or_default(".namespace", "default")
                c.assert_true(
                    False,
                    f"EnvoyFilter {namespace}/{name} patches raw Envoy config — brittle across "
                    f"Istio upgrades; prefer a supported Istio API or review each use"
                )

    return c


if __name__ == "__main__":
    main()
