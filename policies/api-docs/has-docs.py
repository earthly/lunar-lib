from lunar_policy import Check


def check_has_docs(node=None):
    """Check that all API spec files have documentation."""
    c = Check("has-docs", "Ensures all API specs include documentation", node=node)
    with c:
        spec_files = c.get_node(".api.spec_files")
        if not spec_files.exists():
            c.skip("No API collector has run")

        items = spec_files.get_value()
        if not isinstance(items, list) or len(items) == 0:
            c.skip("No spec files detected")

        undocumented = [s["path"] for s in items if not s.get("has_docs", False)]
        c.assert_true(
            len(undocumented) == 0,
            f"Specs missing documentation: {', '.join(undocumented)}. "
            "Add descriptions, summaries, and examples to your API definitions."
        )
    return c


if __name__ == "__main__":
    check_has_docs()
