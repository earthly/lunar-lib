from lunar_policy import Check, variable_or_default

from registry_helpers import describe_registry, is_dependency_source


def check_approved_registries(allowed_registries, node=None):
    """Check that dependencies resolve only from approved package registries."""
    c = Check(
        "approved-registries",
        "Dependencies should resolve only from approved package registries",
        node=node,
    )
    with c:
        allowed = [r.strip().lower() for r in allowed_registries.split(",") if r.strip()]

        if not allowed:
            raise ValueError(
                "Policy misconfiguration: 'allowed_registries' is empty. "
                "An allow-list must contain at least one entry. "
                "Configure allowed registries or exclude this check."
            )

        registries = c.get_node(".dependencies.registries")
        if not registries.exists():
            c.skip("No package-manager configuration collected for this component")

        for entry in registries:
            if not is_dependency_source(entry):
                continue

            host = entry.get_value(".host")
            if host and host.lower() in allowed:
                continue

            c.fail(
                f"{describe_registry(entry)} which is not in allowed registries: "
                f"{', '.join(allowed)}"
            )

    return c


def main(node=None):
    return check_approved_registries(
        variable_or_default("allowed_registries", ""), node=node
    )


if __name__ == "__main__":
    main()
