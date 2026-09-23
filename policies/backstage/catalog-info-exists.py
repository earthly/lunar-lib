from lunar_policy import Check

from catalog_presence import skip_if_no_catalog


def main(node=None):
    c = Check(
        "catalog-info-exists",
        "Repository should have a catalog-info.yaml file",
        node=node,
    )
    with c:
        skip_if_no_catalog(c)

        c.assert_exists(
            ".catalog.native.backstage",
            "No catalog-info.yaml found. Add a catalog-info.yaml file to the repository root "
            "(or customize paths via the collector's `paths` input).",
        )
    return c


if __name__ == "__main__":
    main()
