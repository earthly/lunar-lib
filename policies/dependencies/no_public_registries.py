from lunar_policy import Check

from registry_helpers import describe_registry, is_dependency_source


def check_no_public_registries(node=None):
    """Check that no dependency resolves from a well-known public index."""
    c = Check(
        "no-public-registries",
        "Dependencies should not resolve from public package indexes",
        node=node,
    )
    with c:
        registries = c.get_node(".dependencies.registries")
        if not registries.exists():
            c.skip("No package-manager configuration collected for this component")

        for entry in registries:
            if not is_dependency_source(entry):
                continue

            if not entry.get_value_or_default(".is_public", False):
                continue

            c.fail(
                f"{describe_registry(entry)} is a public package index — "
                "route it through an internal registry or proxy"
            )

    return c


def main(node=None):
    return check_no_public_registries(node=node)


if __name__ == "__main__":
    main()
