from lunar_policy import Check


def check_spec_exists(node=None):
    """Check that at least one API spec file exists."""
    c = Check("spec-exists", "Ensures at least one API spec file exists", node=node)
    with c:
        spec_files = c.get_node(".api.spec_files")
        if not spec_files.exists():
            c.skip("No API collector has run")

        items = spec_files.get_value()
        c.assert_true(
            isinstance(items, list) and len(items) > 0,
            "No API spec files found. Add an OpenAPI, Swagger, protobuf, or "
            "GraphQL SDL file to document your API."
        )
    return c


if __name__ == "__main__":
    check_spec_exists()
