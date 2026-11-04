from lunar_policy import Check

from catalog_presence import fetched_from_catalog, skip_if_no_catalog_file

NO_FILE = (
    "No catalog-info.yaml found. Add a catalog-info.yaml file to the repository root "
    "(or customize paths via the collector's `paths` input)."
)


def main(node=None):
    c = Check(
        "catalog-info-exists",
        "Repository should have a catalog-info.yaml file",
        node=node,
    )
    with c:
        skip_if_no_catalog_file(c)

        c.assert_exists(".catalog.native.backstage", NO_FILE)
        # An entity fetched from the catalog API (catalog_api_fallback) is not a file.
        if fetched_from_catalog(c):
            c.fail(NO_FILE)
    return c


if __name__ == "__main__":
    main()
