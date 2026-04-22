from lunar_policy import Check


def main(node=None):
    c = Check(
        "system-set",
        "catalog-info.yaml should define spec.system",
        node=node,
    )
    with c:
        if not c.exists(".catalog.native.backstage"):
            c.fail(
                "No catalog-info.yaml found. Add the file with a spec.system "
                "reference so this component is grouped under a parent system."
            )
            return c

        system = c.get_value_or_default(".catalog.native.backstage.spec.system", "")
        if not isinstance(system, str) or not system.strip():
            c.fail(
                "spec.system is not set in catalog-info.yaml. Add a system "
                "reference (e.g. `payment-platform`) so this component is "
                "grouped under a parent system for dependency mapping."
            )
    return c


if __name__ == "__main__":
    main()
