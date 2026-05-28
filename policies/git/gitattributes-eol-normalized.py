from lunar_policy import Check


def main(node=None):
    c = Check(
        "gitattributes-eol-normalized",
        "`.gitattributes` should declare EOL normalization (e.g. `* text=auto`)",
        node=node,
    )
    with c:
        attrs = (
            c.get_node(".git.attributes").get_value_or_default(".", None)
        )
        if attrs is None:
            c.skip(
                "No `.gitattributes` file found "
                "(gitattributes-exists covers this case)"
            )
            return c

        if not attrs.get("eol_normalized"):
            c.fail(
                "`.gitattributes` does not declare EOL normalization. Add "
                "`* text=auto` (or equivalent `text` / `eol=` directives) "
                "so Windows checkouts don't produce CRLF diffs."
            )
    return c


if __name__ == "__main__":
    main()
