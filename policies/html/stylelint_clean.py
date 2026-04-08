from lunar_policy import Check, variable_or_default


def stylelint_clean(max_warnings=None, node=None):
    """Ensures Stylelint reports warnings within threshold."""
    if max_warnings is None:
        max_warnings = int(variable_or_default("max_stylelint_warnings", "0"))
    else:
        max_warnings = int(max_warnings)

    c = Check("stylelint-clean", "Ensures Stylelint warnings are within threshold", node=node)
    with c:
        css = c.get_node(".lang.css")
        if not css.exists():
            c.skip("Not a CSS project")

        lint_node = css.get_node(".lint")
        if not lint_node.exists():
            c.skip("Stylelint data not available - ensure html collector has run")

        warnings_node = lint_node.get_node(".warnings")
        if warnings_node.exists() and warnings_node.get_value():
            warning_count = len(warnings_node.get_value())
        else:
            warning_count = 0

        c.assert_less_or_equal(
            warning_count,
            max_warnings,
            f"Found {warning_count} Stylelint issue(s), maximum allowed is {max_warnings}. "
            f"Run 'stylelint' and fix the reported issues."
        )

    return c


if __name__ == "__main__":
    stylelint_clean()
