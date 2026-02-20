from lunar_policy import Check, variable_or_default


def check_clippy_clean(max_warnings=None, node=None):
    """Check that clippy reports no warnings (or fewer than threshold)."""
    if max_warnings is None:
        max_warnings = int(variable_or_default("max_clippy_warnings", "0"))
    else:
        max_warnings = int(max_warnings)

    c = Check("clippy-clean", "Ensures clippy reports no warnings", node=node)
    with c:
        rust = c.get_node(".lang.rust")
        if not rust.exists():
            c.skip("Not a Rust project")

        lint = rust.get_node(".lint")
        if not lint.exists():
            c.skip("Clippy data not collected (is the clippy sub-collector enabled?)")

        warnings = lint.get_node(".warnings")
        count = len(warnings.get_value()) if warnings.exists() and warnings.get_value() else 0

        if count > max_warnings:
            c.fail(
                f"{count} clippy warning(s) found, maximum allowed is {max_warnings}. "
                f"Run 'cargo clippy' and fix all warnings."
            )
    return c


if __name__ == "__main__":
    check_clippy_clean()
