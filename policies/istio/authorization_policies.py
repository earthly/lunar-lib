from lunar_policy import Check


def main(node=None):
    """Requires at least one AuthorizationPolicy in the mesh."""
    c = Check("authorization-policies-defined", "Mesh should define authorization policies", node=node)
    with c:
        mesh = c.get_node(".mesh")
        if not mesh.exists():
            c.skip("No service-mesh configuration found in this repository")

        aps = c.get_node(".mesh.authorization_policies")
        count = len(aps.get_value()) if aps.exists() else 0

        c.assert_true(
            count > 0,
            "No AuthorizationPolicy defined — mTLS authenticates workloads but does not "
            "authorize them; add an AuthorizationPolicy to establish an access-control baseline"
        )

    return c


if __name__ == "__main__":
    main()
