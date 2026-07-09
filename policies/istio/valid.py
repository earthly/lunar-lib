from lunar_policy import Check


def main(node=None):
    """Validates that all Istio resources parse and pass istioctl analyze."""
    c = Check("valid", "All Istio resources should be valid", node=node)
    with c:
        resources = c.get_node(".mesh.resources")
        if not resources.exists():
            c.skip("No Istio resources found in this repository")

        for r in resources:
            path = r.get_value_or_default(".path", "<unknown>")
            kind = r.get_value_or_default(".kind", "resource")
            name = r.get_value_or_default(".name", "<unknown>")
            valid = r.get_value_or_default(".valid", True)
            error = r.get_value_or_default(".error", "istioctl analyze reported an error")

            c.assert_true(valid, f"{path}: {kind} {name} is invalid — {error}")

    return c


if __name__ == "__main__":
    main()
