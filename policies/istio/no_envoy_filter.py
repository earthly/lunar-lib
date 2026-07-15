from lunar_policy import Check

from helpers import mesh_present


def main(node=None):
    """Advisory: flags EnvoyFilter usage (brittle low-level Envoy patching)."""
    c = Check("no-envoy-filter", "Mesh should avoid EnvoyFilter", node=node)
    with c:
        mesh_present(c)

        efs = c.get_node(".mesh.envoy_filters")
        for ef in (efs if efs.exists() else []):
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
