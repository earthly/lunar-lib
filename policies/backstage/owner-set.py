from lunar_policy import Check


def main(node=None):
    c = Check(
        "owner-set",
        "catalog-info.yaml should define spec.owner",
        node=node,
    )
    with c:
        if not c.get_value(".catalog.native.backstage.exists"):
            c.fail(
                "No catalog-info.yaml found. Add the file with a spec.owner so "
                "this component has a designated owner."
            )
            return c

        owner = c.get_value_or_default(".catalog.native.backstage.spec.owner", "")
        if not isinstance(owner, str) or not owner.strip():
            c.fail(
                "spec.owner is not set in catalog-info.yaml. Add an owner "
                "reference (e.g. `team-payments`, `group:infra`, `user:alice`)."
            )
    return c


if __name__ == "__main__":
    main()
