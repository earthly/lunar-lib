from lunar_policy import Check, variable_or_default


def main(node=None):
    """Requires mesh-wide mTLS to be STRICT with no permissive/disable overrides."""
    c = Check("mtls-strict", "Mesh-wide mTLS should be STRICT", node=node)
    with c:
        mesh = c.get_node(".mesh")
        if not mesh.exists():
            c.skip("No service-mesh configuration found in this repository")

        required = (variable_or_default("required_mtls_mode", "STRICT") or "STRICT").upper()

        default_node = c.get_node(".mesh.summary.mtls_default_mode")
        default_mode = default_node.get_value() if default_node.exists() else None

        c.assert_true(
            default_mode == required,
            f"Mesh mTLS default is {default_mode or 'unset'} — set a mesh-wide "
            f"PeerAuthentication (root namespace) with mode: {required}"
        )

        # When STRICT is required, no namespace/workload override may downgrade it.
        if required == "STRICT":
            pas = c.get_node(".mesh.peer_authentications")
            if pas.exists():
                for pa in pas:
                    mode = pa.get_value_or_default(".mode", None)
                    name = pa.get_value_or_default(".name", "<unknown>")
                    namespace = pa.get_value_or_default(".namespace", "default")
                    scope = pa.get_value_or_default(".scope", "namespace")
                    c.assert_true(
                        mode not in ("PERMISSIVE", "DISABLE"),
                        f"PeerAuthentication {namespace}/{name} ({scope} scope) sets mTLS "
                        f"mode {mode} — downgrades encryption below STRICT"
                    )

    return c


if __name__ == "__main__":
    main()
