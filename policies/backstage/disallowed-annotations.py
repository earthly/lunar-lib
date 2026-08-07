from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check(
        "disallowed-annotations",
        "catalog-info.yaml should not declare any disallowed annotations",
        node=node,
    )
    with c:
        disallowed_str = variable_or_default("disallowed_annotations", "")
        disallowed = [a.strip() for a in disallowed_str.split(",") if a.strip()]
        if not disallowed:
            # Opt-in check: with nothing configured there is nothing to enforce.
            c.skip(
                "No disallowed_annotations configured. Set the "
                "`disallowed_annotations` input to forbid annotation keys."
            )

        # Pure deny-check: read defensively so a missing catalog file simply
        # means "nothing disallowed is present" (pass), rather than a failure —
        # the required-* / exists checks already cover a missing file.
        annotations = c.get_value_or_default(
            ".catalog.native.backstage.metadata.annotations", {}
        )
        if not isinstance(annotations, dict):
            annotations = {}

        present = [key for key in disallowed if key in annotations]
        if present:
            c.fail(
                "catalog-info.yaml declares disallowed annotation(s): "
                f"{', '.join(present)}. Remove them from metadata.annotations."
            )
    return c


if __name__ == "__main__":
    main()
