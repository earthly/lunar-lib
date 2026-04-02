from lunar_policy import Check, variable_or_default


def check_spec_version(min_version=None, node=None):
    """Check that REST API specs meet a minimum OpenAPI version."""
    if min_version is None:
        min_version = variable_or_default("min_version", "3")

    c = Check("spec-version", "Ensures OpenAPI specs meet minimum version", node=node)
    with c:
        spec_files = c.get_node(".api.spec_files")
        if not spec_files.exists():
            c.skip("No API collector has run")

        items = spec_files.get_value()
        if not isinstance(items, list) or len(items) == 0:
            c.skip("No spec files detected")

        # Only check REST protocol specs
        rest_specs = [s for s in items if s.get("protocol") == "rest"]
        if len(rest_specs) == 0:
            c.skip("No REST API specs detected")

        min_major = int(min_version)
        outdated = []
        for spec in rest_specs:
            version = str(spec.get("version", "0"))
            try:
                major = int(version.split(".")[0])
            except (ValueError, IndexError):
                major = 0
            if major < min_major:
                outdated.append(f"{spec['path']} (v{version})")

        c.assert_true(
            len(outdated) == 0,
            f"Specs below OpenAPI {min_version}.x: {', '.join(outdated)}. "
            f"Migrate to OpenAPI {min_version}.x+ using swagger2openapi or similar."
        )
    return c


if __name__ == "__main__":
    check_spec_version()
