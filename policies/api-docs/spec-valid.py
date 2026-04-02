from lunar_policy import Check


def check_spec_valid(node=None):
    """Check that all API spec files parse without errors."""
    c = Check("spec-valid", "Ensures all API spec files are valid", node=node)
    with c:
        spec_files = c.get_node(".api.spec_files")
        if not spec_files.exists():
            c.skip("No API collector has run")

        items = spec_files.get_value()
        if not isinstance(items, list) or len(items) == 0:
            c.skip("No spec files detected")

        invalid = [s["path"] for s in items if not s.get("valid", False)]
        c.assert_true(
            len(invalid) == 0,
            f"Invalid spec files: {', '.join(invalid)}. "
            "Fix syntax errors so specs parse cleanly."
        )
    return c


if __name__ == "__main__":
    check_spec_valid()
