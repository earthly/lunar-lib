from lunar_policy import Check


def main(node=None):
    """Requires ingress Gateways to use TLS (or redirect plain HTTP to HTTPS)."""
    c = Check("gateway-tls", "Gateway servers should use TLS", node=node)
    with c:
        gateways = c.get_node(".mesh.gateways")
        if not gateways.exists():
            c.skip("No Istio Gateways found in this repository")

        for gw in gateways:
            name = gw.get_value_or_default(".name", "<unknown>")
            namespace = gw.get_value_or_default(".namespace", "default")

            servers = gw.get_node(".servers")
            if not servers.exists():
                continue

            for s in servers:
                port = s.get_value_or_default(".port", "?")
                protocol = (s.get_value_or_default(".protocol", "") or "").upper()
                tls_mode = s.get_value_or_default(".tls_mode", None)
                https_redirect = s.get_value_or_default(".https_redirect", False)

                if protocol == "HTTP":
                    c.assert_true(
                        https_redirect is True,
                        f"Gateway {namespace}/{name} port {port} serves plaintext HTTP "
                        f"without httpsRedirect: true"
                    )
                elif protocol in ("HTTPS", "TLS"):
                    c.assert_true(
                        tls_mode is not None,
                        f"Gateway {namespace}/{name} port {port} is {protocol} but has no "
                        f"tls config"
                    )
                # Other protocols (TCP, GRPC, MONGO, ...) are out of scope for this check.

    return c


if __name__ == "__main__":
    main()
