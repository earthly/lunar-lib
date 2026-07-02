import fnmatch

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check(
        "disallowed-tag-patterns",
        "catalog-info.yaml tags should not match any disallowed pattern",
        node=node,
    )
    with c:
        patterns_str = variable_or_default("disallowed_tag_patterns", "")
        patterns = [p.strip() for p in patterns_str.split(",") if p.strip()]
        if not patterns:
            # Opt-in check: with nothing configured there is nothing to enforce.
            c.skip(
                "No disallowed_tag_patterns configured. Set the "
                "`disallowed_tag_patterns` input to forbid tag patterns."
            )

        # Pure deny-check: read defensively so a missing catalog file simply
        # means "no disallowed tag is present" (pass), rather than a failure.
        tags = c.get_value_or_default(".catalog.native.backstage.metadata.tags", [])
        if not isinstance(tags, list):
            tags = []
        # Backstage tags are lowercase by spec; normalize both sides so matching
        # is deterministic regardless of platform case-folding.
        tags = [str(t).strip().lower() for t in tags if str(t).strip()]

        violations = []
        for p in patterns:
            matching = [t for t in tags if fnmatch.fnmatchcase(t, p.lower())]
            if matching:
                violations.append(f"{p} ({', '.join(matching)})")
        if violations:
            c.fail(
                "catalog-info.yaml has tag(s) matching disallowed pattern(s): "
                f"{'; '.join(violations)}. Remove them from metadata.tags."
            )
    return c


if __name__ == "__main__":
    main()
