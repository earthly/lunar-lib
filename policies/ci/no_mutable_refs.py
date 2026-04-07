from lunar_policy import Check

MUTABLE_REFS = {"main", "master", "latest", "develop", "dev", "trunk"}


def main(node=None):
    c = Check(
        "no-mutable-refs",
        "No third-party CI dependencies reference mutable refs",
        node=node,
    )
    with c:
        deps_node = c.get_node(".ci.dependencies")
        if not deps_node.exists():
            c.skip("No CI dependency data found — ensure a CI collector is configured")

        items_node = deps_node.get_node(".items")
        if not items_node.exists():
            c.skip("No dependency item data available")

        items = items_node.get_value()
        if not isinstance(items, list):
            c.skip("Dependency items not in expected format")

        mutable = []
        for item in items:
            if item.get("party") != "3rd":
                continue
            ref = item.get("ref", "")
            if ref.lower() in MUTABLE_REFS:
                mutable.append(f"{item.get('name', '?')}@{ref}")

        if mutable:
            refs = ", ".join(mutable[:10])
            suffix = ""
            if len(mutable) > 10:
                suffix = f" (and {len(mutable) - 10} more)"
            c.fail(
                f"{len(mutable)} third-party CI dependency(ies) using mutable "
                f"refs: {refs}{suffix}"
            )

    return c


if __name__ == "__main__":
    main()
