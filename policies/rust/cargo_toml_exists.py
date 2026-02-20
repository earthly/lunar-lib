from lunar_policy import Check


def check_cargo_toml_exists(node=None):
    """Check that Cargo.toml file exists in a Rust project."""
    c = Check("cargo-toml-exists", "Ensures Cargo.toml exists", node=node)
    with c:
        rust = c.get_node(".lang.rust")
        if not rust.exists():
            c.skip("Not a Rust project")

        cargo_toml = rust.get_node(".cargo_toml_exists")
        if not cargo_toml.exists():
            c.skip("Cargo data not available - ensure rust collector has run")

        c.assert_true(
            cargo_toml.get_value(),
            "Cargo.toml not found. Initialize with 'cargo init' or 'cargo new <name>'"
        )
    return c


if __name__ == "__main__":
    check_cargo_toml_exists()
