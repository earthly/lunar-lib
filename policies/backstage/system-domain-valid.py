from lunar_policy import Check

from catalog_presence import skip_if_no_catalog


def main(node=None):
    c = Check(
        "system-domain-valid",
        "spec.system should resolve to a System in the Backstage catalog that "
        "belongs to a Domain that exists",
        node=node,
    )
    with c:
        skip_if_no_catalog(c)

        if not c.exists(".catalog.native.backstage"):
            c.fail(
                "No catalog-info.yaml found. Add the file with a spec.system "
                "whose System belongs to an existing Domain."
            )
            return c

        system = c.get_value_or_default(".catalog.native.backstage.spec.system", "")
        if not isinstance(system, str) or not system.strip():
            c.skip(
                "catalog-info.yaml declares no spec.system, so there is no "
                "System to follow to a Domain. `system-set` reports a missing "
                "spec.system."
            )

        if not c.exists(".catalog.native.backstage.refs.checked"):
            c.skip(
                "Backstage referential integrity is not configured. Set the "
                "`backstage` collector's `backstage_url` input to check this "
                "component's System and its Domain against the live catalog."
            )

        ref = c.get_value_or_default(".catalog.native.backstage.refs.system", None)
        if not isinstance(ref, dict):
            c.skip(
                f"The `backstage` collector recorded no lookup of system "
                f"'{system}', so there is nothing to check."
            )
        name = ref.get("name", system)

        # A failed lookup isn't proof the entity is missing: skip, so an outage
        # or a rejected credential doesn't fail every component.
        if "exists" not in ref:
            c.skip(
                f"Could not look up system '{name}' in Backstage "
                f"({ref.get('error', 'unknown error')}); skipping rather than "
                "failing on a lookup error."
            )

        if not ref.get("exists"):
            c.fail(
                f"System '{name}' (referenced by spec.system) does not exist in "
                "the Backstage catalog. Fix spec.system to match an existing "
                "System's metadata.name, or register the System in Backstage."
            )
            return c

        # The domain failures name the System: spec.domain lives on that
        # entity, whose catalog file is usually another team's.
        if ref.get("has_domain") is False:
            c.fail(
                f"System '{name}' (referenced by spec.system) does not belong to "
                "any domain. This component's catalog-info.yaml is not at fault "
                f"— set spec.domain on the '{name}' System entity to an existing "
                "Domain."
            )
            return c

        # Collectors before has_domain still write system_domain for a System
        # that has a domain, so only its absence leaves the domain unknown.
        domain = c.get_value_or_default(
            ".catalog.native.backstage.refs.system_domain", None
        )
        if not isinstance(domain, dict):
            c.skip(
                f"Could not tell whether system '{name}' belongs to a domain: "
                "the `backstage` collector predates this check, or Backstage "
                "returned a System entity it could not read."
            )
        domain_name = domain.get("name", "?")

        if "exists" not in domain:
            c.skip(
                f"Could not look up domain '{domain_name}' of system '{name}' "
                f"in Backstage ({domain.get('error', 'unknown error')}); "
                "skipping rather than failing on a lookup error."
            )

        if not domain.get("exists"):
            c.fail(
                f"System '{name}' (referenced by spec.system) belongs to domain "
                f"'{domain_name}', which does not exist in the Backstage catalog. "
                "This component's catalog-info.yaml is not at fault — fix "
                f"spec.domain on the '{name}' System entity to match an existing "
                "Domain, or register the Domain in Backstage."
            )
    return c


if __name__ == "__main__":
    main()
