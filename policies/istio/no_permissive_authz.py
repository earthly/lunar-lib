from lunar_policy import Check


def main(node=None):
    """Fails when an AuthorizationPolicy grants blanket (allow-all) access."""
    c = Check("no-permissive-authz", "No AuthorizationPolicy should grant blanket access", node=node)
    with c:
        aps = c.get_node(".mesh.authorization_policies")
        if not aps.exists():
            c.skip("No AuthorizationPolicy resources found in this repository")

        for ap in aps:
            name = ap.get_value_or_default(".name", "<unknown>")
            namespace = ap.get_value_or_default(".namespace", "default")
            allows_all = ap.get_value_or_default(".allows_all", False)

            c.assert_true(
                allows_all is not True,
                f"AuthorizationPolicy {namespace}/{name} has an ALLOW rule with no "
                f"source/operation/condition constraints — it grants blanket access"
            )

    return c


if __name__ == "__main__":
    main()
