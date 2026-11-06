from lunar_policy import Check

from catalog_presence import FETCHED_NO_FILE, fetched_counts_as_no_file, skip_if_no_catalog_file

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
        # An entity fetched from the catalog API (catalog_api_fallback) is not a
        # file, unless require_catalog_file is off.
        if fetched_counts_as_no_file(c):
            c.fail(FETCHED_NO_FILE)
    return c


if __name__ == "__main__":
    main()
