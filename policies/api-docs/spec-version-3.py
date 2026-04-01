from lunar_policy import Check

with Check("spec-version-3", "All API specs should use OpenAPI 3.x (not Swagger 2.0)") as c:
    specs = c.get_node(".api.specs")
    if not specs.exists():
        c.skip("No API spec files detected")

    for spec in specs:
        path = spec.get_value_or_default(".path", "<unknown>")
        spec_type = spec.get_value_or_default(".type", "unknown")
        version = spec.get_value_or_default(".version", "unknown")

        if spec_type == "swagger":
            c.fail(
                f"{path}: uses Swagger {version} — migrate to OpenAPI 3.x "
                f"(see https://swagger.io/docs/specification/v3_0/about/)"
            )
