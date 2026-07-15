from lunar_policy import Check


def main(node=None):
    c = Check(
        "domain-exists",
        "spec.domain should reference a domain that exists in the Backstage catalog",
        node=node,
    )
    with c:
        # Referential integrity is opt-in: it only runs when the `backstage`
        # collector is configured with `backstage_url`, which it signals by
        # writing `.refs.checked`. Without it there is nothing to verify, so
        # skip (→ pass), mirroring the required-*/disallowed-* opt-in checks.
        # (A durable "pending" isn't available — post-collection the SDK
        # resolves a data-less check to fail/error, not pending.)
        if not c.exists(".catalog.native.backstage.refs.checked"):
            c.skip(
                "Backstage referential integrity is not configured. Set the "
                "`backstage` collector's `backstage_url` input to verify "
                "spec.domain against the live catalog."
            )
            return c

        ref = c.get_value_or_default(".catalog.native.backstage.refs.domain", None)
        if not isinstance(ref, dict):
            # No spec.domain declared, so there is nothing to cross-check.
            # `domain-set`/`system-set` own "should the field be set".
            return c

        if "exists" not in ref:
            # Transient lookup failure (recorded as {name, error}); referential
            # integrity could not be determined, so skip rather than false-fail
            # on a Backstage outage.
            name = ref.get("name", "?")
            err = ref.get("error", "unknown error")
            c.skip(
                f"Could not verify domain '{name}' against Backstage ({err}); "
                "skipping rather than failing on a transient error."
            )
            return c

        if not ref.get("exists"):
            name = ref.get("name", "?")
            c.fail(
                f"Domain '{name}' referenced in catalog-info.yaml does not exist "
                "in the Backstage catalog. Fix spec.domain to match an existing "
                "Domain's metadata.name, or register the Domain in Backstage."
            )
    return c


if __name__ == "__main__":
    main()
