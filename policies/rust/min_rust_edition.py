from lunar_policy import Check, variable_or_default


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

        try:
            actual = int(edition)
            minimum = int(min_edition)
        except (ValueError, TypeError):
            c.fail(f"Could not parse edition: '{edition}' or minimum: '{min_edition}'")

        if actual < minimum:
            c.fail(
                f"Rust edition {edition} is below minimum {min_edition}. "
                f"Update edition in Cargo.toml to '{min_edition}' or later."
            )
    return c


if __name__ == "__main__":
    check_min_rust_edition()
