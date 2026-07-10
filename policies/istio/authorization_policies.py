from lunar_policy import Check

from helpers import mesh_present


def main(node=None):
    """Requires at least one AuthorizationPolicy in the mesh."""
    c = Check("authorization-policies-defined", "Mesh should define authorization policies", node=node)
    with c:
        mesh_present(c)

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
