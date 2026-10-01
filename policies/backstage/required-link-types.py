from lunar_policy import Check, variable_or_default

from catalog_presence import skip_if_no_catalog


def main(node=None):
    c = Check(
        "required-link-types",
        "catalog-info.yaml should declare a link of each required type",
        node=node,
    )
    with c:
        types_str = variable_or_default("required_link_types", "")
        required = list(
            dict.fromkeys(t.strip() for t in types_str.split(",") if t.strip())
        )
        if not required:
            # Opt-in check: with nothing configured there is nothing to enforce.
            c.skip(
                "No required_link_types configured. Set the "
                "`required_link_types` input to require typed metadata.links entries."
            )

        skip_if_no_catalog(c)

        if not c.exists(".catalog.native.backstage"):
            c.fail(
                "No catalog-info.yaml found, so required link types cannot be "
                f"verified. Required: {', '.join(required)}. Add a "
                "catalog-info.yaml with a link of each type under metadata.links."
            )
            return c

        links = c.get_value_or_default(".catalog.native.backstage.metadata.links", [])
        if not isinstance(links, list):
            links = []
        # Link types are free-form in Backstage, so match exactly; title and url
        # are not consulted.
        present = list(
            dict.fromkeys(
                link["type"].strip()
                for link in links
                if isinstance(link, dict)
                and isinstance(link.get("type"), str)
                and link["type"].strip()
            )
        )

        missing = [t for t in required if t not in present]
        if missing:
            c.fail(
                "catalog-info.yaml has no metadata.links entry of type: "
                f"{', '.join(missing)}. Present link types: "
                f"{', '.join(present) if present else '(none)'}. Add a link "
                "with each missing `type` under metadata.links."
            )
    return c


if __name__ == "__main__":
    main()
