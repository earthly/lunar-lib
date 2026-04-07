from lunar_policy import Check


def main(node=None):
    c = Check(
        "dependencies-pinned",
        "All third-party CI dependencies use SHA or tag pins",
        node=node,
    )
    with c:
        deps_node = c.get_node(".ci.dependencies")
        if not deps_node.exists():
            c.skip("No CI dependency data found — ensure a CI collector is configured")

        unpinned_node = deps_node.get_node(".third_party_unpinned")
        if not unpinned_node.exists():
            c.skip("No pinning data available")

        unpinned = unpinned_node.get_value()

        if isinstance(unpinned, list) and len(unpinned) > 0:
            refs = ", ".join(unpinned[:10])
            suffix = ""
            if len(unpinned) > 10:
                suffix = f" (and {len(unpinned) - 10} more)"
            c.fail(
                f"{len(unpinned)} third-party CI dependency(ies) not pinned to "
                f"SHA or tag: {refs}{suffix}"
            )

    return c


if __name__ == "__main__":
    main()
