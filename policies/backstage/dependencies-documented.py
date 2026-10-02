from lunar_policy import Check, variable_or_default

from catalog_presence import skip_if_no_catalog

EXAMPLE = "(e.g. `resource:payments-db`, `component:auth-service`)"


def main(node=None):
    c = Check(
        "dependencies-documented",
        "catalog-info.yaml should declare the component's dependencies",
        node=node,
    )
    with c:
        if variable_or_default("require_dependencies", "false").strip().lower() != "true":
            # Opt-in, so a whole-bundle import doesn't start failing every
            # component that declares no dependencies.
            c.skip(
                'Not enforced. Set the `require_dependencies` input to "true" '
                "to require declared dependencies."
            )

        skip_if_no_catalog(c)

        annotation = variable_or_default("dependencies_annotation", "").strip()
        where = f"under spec.dependsOn {EXAMPLE}"
        if annotation:
            where += f", or as a comma-separated list in the `{annotation}` annotation"

        if not c.exists(".catalog.native.backstage"):
            c.fail(
                "No catalog-info.yaml found, so dependencies cannot be verified. "
                f"Add a catalog-info.yaml that lists them {where}."
            )
            return c

        # Any non-empty entry counts; targets are not resolved against the catalog.
        depends_on = c.get_value_or_default(
            ".catalog.native.backstage.spec.dependsOn", []
        )
        if isinstance(depends_on, list) and any(
            isinstance(d, str) and d.strip() for d in depends_on
        ):
            return c

        if annotation:
            annotations = c.get_value_or_default(
                ".catalog.native.backstage.metadata.annotations", {}
            )
            value = annotations.get(annotation) if isinstance(annotations, dict) else None
            if isinstance(value, str) and any(p.strip() for p in value.split(",")):
                return c

        c.fail(
            "catalog-info.yaml declares no dependencies. List the entities this "
            f"component depends on {where}."
        )
    return c


if __name__ == "__main__":
    main()
