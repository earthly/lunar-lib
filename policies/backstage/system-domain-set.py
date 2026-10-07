from lunar_policy import Check

from catalog_presence import skip_if_no_catalog


def main(node=None):
    c = Check(
        "system-domain-set",
        "the system referenced by spec.system should belong to a domain in "
        "the Backstage catalog",
        node=node,
    )
    with c:
        skip_if_no_catalog(c)

        # Needs the live System entity, so like the other referential-integrity
        # checks it only runs when the `backstage` collector has `backstage_url`.
        if not c.exists(".catalog.native.backstage.refs.checked"):
            c.skip(
                "Backstage referential integrity is not configured. Set the "
                "`backstage` collector's `backstage_url` input to check that "
                "this component's system belongs to a domain."
            )
            return c

        # With no System to read a domain off, skip rather than pass: a pass
        # would claim a domain was checked. The checks that own those two
        # failures, `system-set` and `system-exists`, report them.
        ref = c.get_value_or_default(".catalog.native.backstage.refs.system", None)
        if not isinstance(ref, dict):
            c.skip(
                "catalog-info.yaml declares no spec.system, so there is no "
                "System to check for a domain. `system-set` reports a missing "
                "spec.system."
            )
            return c

        name = ref.get("name", "?")

        if "exists" not in ref:
            err = ref.get("error", "unknown error")
            c.skip(
                f"Could not look up system '{name}' in Backstage ({err}); "
                "skipping rather than failing on a transient error."
            )
            return c

        if not ref.get("exists"):
            c.skip(
                f"System '{name}' (referenced by spec.system) does not exist in "
                "Backstage, so there is no domain to check. `system-exists` "
                "reports the missing System."
            )
            return c

        if "has_domain" not in ref:
            c.skip(
                f"Could not tell whether system '{name}' belongs to a domain: "
                "the `backstage` collector predates this check, or Backstage "
                "returned a System entity it could not read."
            )
            return c

        if not ref["has_domain"]:
            # Name the System: spec.domain lives on that entity, whose catalog
            # file is usually another team's, not on this component.
            c.fail(
                f"System '{name}' (referenced by spec.system) does not belong to "
                "any domain. This component's catalog-info.yaml is not at fault "
                f"— set spec.domain on the '{name}' System entity to an existing "
                "Domain."
            )
    return c


if __name__ == "__main__":
    main()
