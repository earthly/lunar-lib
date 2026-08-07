import fnmatch

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check(
        "required-tag-patterns",
        "catalog-info.yaml tags should match all required patterns",
        node=node,
    )
    with c:
        patterns_str = variable_or_default("required_tag_patterns", "")
        patterns = [p.strip() for p in patterns_str.split(",") if p.strip()]
        if not patterns:
            # Opt-in check: with nothing configured there is nothing to enforce.
            c.skip(
                "No required_tag_patterns configured. Set the "
                "`required_tag_patterns` input to enforce tag patterns."
            )

        if not c.exists(".catalog.native.backstage"):
            c.fail(
                "No catalog-info.yaml found, so required tag patterns cannot be "
                f"verified. Required patterns: {', '.join(patterns)}. Add a "
                "catalog-info.yaml with matching tags under metadata.tags."
            )
            return c

        tags = c.get_value_or_default(".catalog.native.backstage.metadata.tags", [])
        if not isinstance(tags, list):
            tags = []
        # Backstage tags are lowercase by spec; normalize both sides so matching
        # is deterministic regardless of platform case-folding.
        tags = [str(t).strip().lower() for t in tags if str(t).strip()]

        unmatched = [
            p for p in patterns
            if not any(fnmatch.fnmatchcase(t, p.lower()) for t in tags)
        ]
        if unmatched:
            c.fail(
                "catalog-info.yaml has no tag matching required pattern(s): "
                f"{', '.join(unmatched)}. Present tags: "
                f"{', '.join(tags) if tags else '(none)'}. Add matching tags "
                "under metadata.tags."
            )
    return c


if __name__ == "__main__":
    main()
