from lunar_policy import Check


def main(node=None):
    c = Check(
        "system-domain-exists",
        "the domain of the system referenced by spec.system should exist in "
        "the Backstage catalog",
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
                "`backstage` collector's `backstage_url` input to verify the "
                "domain of this component's system against the live catalog."
            )
            return c

        ref = c.get_value_or_default(
            ".catalog.native.backstage.refs.system_domain", None
        )
        if not isinstance(ref, dict):
            # The collector writes this entry only when it got all the way to a
            # domain: the component declares a spec.system, that system resolved
            # in Backstage, and the system itself declares a spec.domain. Any
            # earlier stop leaves nothing to cross-check here — a missing or
            # unresolvable system is `system-exists`'s failure to report, and a
            # system that belongs to no domain is not this check's business.
            return c

        name = ref.get("name", "?")
        via = ref.get("via_system", "?")

        if "exists" not in ref:
            # Transient lookup failure (recorded as {name, error}); referential
            # integrity could not be determined, so skip rather than false-fail
            # on a Backstage outage.
            err = ref.get("error", "unknown error")
            c.skip(
                f"Could not verify domain '{name}' of system '{via}' against "
                f"Backstage ({err}); skipping rather than failing on a "
                "transient error."
            )
            return c

        if not ref.get("exists"):
            # Name the system, not just the domain: this component's
            # catalog-info.yaml has nothing to correct — spec.domain lives on
            # the System entity, whose catalog file is typically owned by
            # another team. Without the system name there is nowhere to go.
            c.fail(
                f"System '{via}' (referenced by spec.system) belongs to domain "
                f"'{name}', which does not exist in the Backstage catalog. "
                f"This component's catalog-info.yaml is not at fault — fix "
                f"spec.domain on the '{via}' System entity to match an existing "
                "Domain, or register the Domain in Backstage."
            )
    return c


if __name__ == "__main__":
    main()
