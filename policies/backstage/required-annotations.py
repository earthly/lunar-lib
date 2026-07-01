from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check(
        "required-annotations",
        "catalog-info.yaml should declare all required annotations",
        node=node,
    )
    with c:
        required_str = variable_or_default("required_annotations", "")
        required = [a.strip() for a in required_str.split(",") if a.strip()]
        if not required:
            # Opt-in check: with nothing configured there is nothing to enforce.
            c.skip(
                "No required_annotations configured. Set the "
                "`required_annotations` input to enforce annotation keys."
            )

        if not c.exists(".catalog.native.backstage"):
            c.fail(
                "No catalog-info.yaml found, so required annotations cannot be "
                f"verified. Required: {', '.join(required)}. Add a "
                "catalog-info.yaml with these annotations under metadata.annotations."
            )
            return c

        annotations = c.get_value_or_default(
            ".catalog.native.backstage.metadata.annotations", {}
        )
        if not isinstance(annotations, dict):
            annotations = {}

        missing = [
            key for key in required
            if not str(annotations.get(key, "")).strip()
        ]
        if missing:
            c.fail(
                "catalog-info.yaml is missing required annotation(s): "
                f"{', '.join(missing)}. Add them under metadata.annotations."
            )
    return c


if __name__ == "__main__":
    main()
