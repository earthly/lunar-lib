from lunar_policy import Check, variable_or_default


def htmlhint_clean(max_warnings=None, node=None):
    """Ensures HTMLHint reports warnings within threshold."""
    if max_warnings is None:
        max_warnings = int(variable_or_default("max_htmlhint_warnings", "0"))
    else:
        max_warnings = int(max_warnings)

    c = Check("htmlhint-clean", "Ensures HTMLHint warnings are within threshold", node=node)
    with c:
        html = c.get_node(".lang.html")
        if not html.exists():
            c.skip("Not an HTML project")

        lint_node = html.get_node(".lint")
        if not lint_node.exists():
            c.skip("HTMLHint data not available - ensure html collector has run")

        warnings_node = lint_node.get_node(".warnings")
        if warnings_node.exists() and warnings_node.get_value():
            warning_count = len(warnings_node.get_value())
        else:
            warning_count = 0

        c.assert_less_or_equal(
            warning_count,
            max_warnings,
            f"Found {warning_count} HTMLHint warning(s), maximum allowed is {max_warnings}. "
            f"Run 'htmlhint' and fix the reported issues."
        )

    return c


if __name__ == "__main__":
    htmlhint_clean()
