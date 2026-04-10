from lunar_policy import Check, variable_or_default

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2, "style": 3}


def shellcheck_clean(max_warnings=None, min_severity=None, node=None):
    """Ensures ShellCheck issues at or above min_severity are within threshold."""
    if max_warnings is None:
        max_warnings = int(variable_or_default("max_shellcheck_warnings", "0"))
    else:
        max_warnings = int(max_warnings)

    if min_severity is None:
        min_severity = variable_or_default("min_severity", "error")

    min_level = SEVERITY_ORDER.get(min_severity, 0)

    c = Check("shellcheck-clean", "Ensures ShellCheck issues are within threshold", node=node)
    with c:
        shell = c.get_node(".lang.shell")
        if not shell.exists():
            c.skip("No shell scripts detected")

        lint_node = shell.get_node(".lint")
        if not lint_node.exists():
            c.skip("ShellCheck data not available - ensure shell collector has run")

        warnings_node = lint_node.get_node(".warnings")
        if warnings_node.exists() and warnings_node.get_value():
            all_warnings = warnings_node.get_value()
            # Filter by severity
            filtered = [
                w for w in all_warnings
                if SEVERITY_ORDER.get(w.get("severity", ""), 99) <= min_level
            ]
            warning_count = len(filtered)
        else:
            warning_count = 0

        c.assert_less_or_equal(
            warning_count,
            max_warnings,
            f"{warning_count} ShellCheck issue(s) found at severity '{min_severity}' or above, "
            f"maximum allowed is {max_warnings}. "
            f"Run 'shellcheck' on your scripts and fix all issues."
        )

    return c


if __name__ == "__main__":
    shellcheck_clean()
