from lunar_policy import Check, variable_or_default

from constraints import parse_required_annotations, validate_value


def main(node=None):
    c = Check(
        "required-annotations",
        "catalog-info.yaml should declare all required annotations",
        node=node,
    )
    with c:
        raw = variable_or_default("required_annotations", "")
        # A malformed input or constraint spec raises ConstraintConfigError
        # (a ValueError), which the Check surfaces as an error — deliberately,
        # so a broken policy config never silently passes.
        entries = parse_required_annotations(raw)
        if not entries:
            # Opt-in check: with nothing configured there is nothing to enforce.
            c.skip(
                "No required_annotations configured. Set the "
                "`required_annotations` input to enforce annotation keys."
            )

        keys = [entry["key"] for entry in entries]
        if not c.exists(".catalog.native.backstage"):
            c.fail(
                "No catalog-info.yaml found, so required annotations cannot be "
                f"verified. Required: {', '.join(keys)}. Add a "
                "catalog-info.yaml with these annotations under metadata.annotations."
            )
            return c

        annotations = c.get_value_or_default(
            ".catalog.native.backstage.metadata.annotations", {}
        )
        if not isinstance(annotations, dict):
            annotations = {}

        for entry in entries:
            key = entry["key"]
            raw_value = annotations.get(key)
            if raw_value is None or not str(raw_value).strip():
                c.fail(
                    f'catalog-info.yaml is missing required annotation "{key}". '
                    "Add it under metadata.annotations."
                )
                continue

            constraints = entry["constraints"]
            if constraints:
                message = validate_value(key, raw_value, constraints)
                if message:
                    c.fail("catalog-info.yaml " + message)
    return c


if __name__ == "__main__":
    main()
