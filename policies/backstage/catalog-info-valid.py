from lunar_policy import Check

from catalog_presence import (
    FETCHED_NO_FILE,
    fetched_counts_as_no_file,
    fetched_from_catalog,
    skip_if_no_catalog_file,
)


def main(node=None):
    c = Check(
        "catalog-info-valid",
        "catalog-info.yaml should pass Backstage schema and syntax checks",
        node=node,
    )
    with c:
        skip_if_no_catalog_file(c)

        if not c.exists(".catalog.native.backstage"):
            c.fail(
                "No catalog-info.yaml found. Add a catalog-info.yaml file to "
                "the repository root so Backstage can register this component."
            )
            return c

        if fetched_counts_as_no_file(c):
            c.fail(FETCHED_NO_FILE)
            return c

        # An accepted fetched entity has no file to lint, and Backstage already
        # validated it on ingestion.
        if fetched_from_catalog(c):
            return c

        if c.get_value(".catalog.native.backstage.valid"):
            return c

        errors = c.get_value_or_default(".catalog.native.backstage.errors", [])
        if not errors:
            c.fail("catalog-info.yaml has lint errors but no details were reported")
            return c

        for err in errors:
            if err.get("severity") != "error":
                continue
            line = err.get("line", "?")
            message = err.get("message", "Unknown error")
            c.fail(f"catalog-info.yaml (line {line}): {message}")
    return c


if __name__ == "__main__":
    main()
