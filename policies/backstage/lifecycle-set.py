from lunar_policy import Check


def main(node=None):
    c = Check(
        "lifecycle-set",
        "catalog-info.yaml should define spec.lifecycle",
        node=node,
    )
    with c:
        if not c.exists(".catalog.native.backstage"):
            c.fail(
                "No catalog-info.yaml found. Add the file with a spec.lifecycle "
                "stage (e.g. `production`, `experimental`, `deprecated`)."
            )
            return c

        lifecycle = c.get_value_or_default(
            ".catalog.native.backstage.spec.lifecycle", ""
        )
        if not isinstance(lifecycle, str) or not lifecycle.strip():
            c.fail(
                "spec.lifecycle is not set in catalog-info.yaml. Add a lifecycle "
                "stage (e.g. `production`, `experimental`, `deprecated`) so "
                "operational expectations are clear."
            )
    return c


if __name__ == "__main__":
    main()
