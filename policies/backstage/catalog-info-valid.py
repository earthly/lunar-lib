from lunar_policy import Check


def main(node=None):
    c = Check(
        "catalog-info-valid",
        "catalog-info.yaml should pass Backstage schema and syntax checks",
        node=node,
    )
    with c:
        if not c.get_value(".catalog.native.backstage.exists"):
            c.fail(
                "No catalog-info.yaml found. Add a catalog-info.yaml file to "
                "the repository root so Backstage can register this component."
            )
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
