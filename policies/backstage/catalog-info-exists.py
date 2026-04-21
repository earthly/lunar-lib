from lunar_policy import Check


def main(node=None):
    c = Check(
        "catalog-info-exists",
        "Repository should have a catalog-info.yaml file",
        node=node,
    )
    with c:
        c.assert_true(
            c.get_value(".catalog.native.backstage.exists"),
            "No catalog-info.yaml found. Add a catalog-info.yaml file to the repository root "
            "(or customize paths via the collector's `paths` input).",
        )
    return c


if __name__ == "__main__":
    main()
