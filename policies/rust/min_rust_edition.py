from lunar_policy import Check, variable_or_default

EDITION_ORDER = ["2015", "2018", "2021", "2024"]


def check_min_rust_edition(min_edition=None, node=None):
    """Check that Rust edition meets minimum requirement."""
    if min_edition is None:
        min_edition = variable_or_default("min_rust_edition", "2021")

    c = Check("min-rust-edition", "Ensures Rust edition meets minimum", node=node)
    with c:
        rust = c.get_node(".lang.rust")
        if not rust.exists():
            c.skip("Not a Rust project")

        edition_node = rust.get_node(".edition")
        if not edition_node.exists():
            c.skip("Rust edition not detected")

        edition = str(edition_node.get_value())

        if edition not in EDITION_ORDER:
            c.fail(f"Unknown Rust edition '{edition}'")

        if min_edition not in EDITION_ORDER:
            c.fail(f"Unknown minimum edition '{min_edition}'")

        if EDITION_ORDER.index(edition) < EDITION_ORDER.index(min_edition):
            c.fail(
                f"Rust edition {edition} is below minimum {min_edition}. "
                f"Update edition in Cargo.toml to '{min_edition}' or later."
            )
    return c


if __name__ == "__main__":
    check_min_rust_edition()
