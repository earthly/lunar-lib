from lunar_policy import Check

from catalog_presence import skip_if_no_catalog


def main(node=None):
    c = Check(
        "system-valid",
        "spec.system should be set and resolve to a System in the Backstage catalog",
        node=node,
    )
    with c:
        skip_if_no_catalog(c)

        if not c.exists(".catalog.native.backstage"):
            c.fail(
                "No catalog-info.yaml found. Add the file with a spec.system "
                "that names a System registered in Backstage."
            )
            return c

        system = c.get_value_or_default(".catalog.native.backstage.spec.system", "")
        if not isinstance(system, str) or not system.strip():
            c.fail(
                "spec.system is not set in catalog-info.yaml. Add a system "
                "reference (e.g. `payment-platform`) that names a System "
                "registered in Backstage."
            )
            return c

        if not c.exists(".catalog.native.backstage.refs.checked"):
            c.skip(
                "Backstage referential integrity is not configured, so only "
                "spec.system being set was checked. Set the `backstage` "
                "collector's `backstage_url` input to also check that it "
                "resolves to a System."
            )

        ref = c.get_value_or_default(".catalog.native.backstage.refs.system", None)
        if not isinstance(ref, dict):
            c.skip(
                f"The `backstage` collector recorded no lookup of system "
                f"'{system}', so there is nothing to check."
            )
        name = ref.get("name", system)

        # A failed lookup isn't proof the System is missing: skip, so an outage
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


if __name__ == "__main__":
    main()
