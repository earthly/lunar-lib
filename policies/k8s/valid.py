from lunar_policy import Check


def main(node=None):
    """Validates that all K8s manifests are syntactically correct."""
    c = Check("valid", "All K8s manifests should be valid", node=node)
    with c:
        manifests = c.get_node(".k8s.manifests")
        if not manifests.exists():
            c.skip("No Kubernetes manifests found in this repository")
            return c

        for manifest in manifests:
            path = manifest.get_value_or_default(".path", "<unknown>")
            valid = manifest.get_value_or_default(".valid", False)
            error = manifest.get_value_or_default(".error", "Unknown validation error")

            c.assert_true(valid, f"{path}: {error}")

    return c


if __name__ == "__main__":
    main()

