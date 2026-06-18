from lunar_policy import Check, variable_or_default


def cppcheck_clean(max_warnings=None, node=None):
    """Ensures cppcheck reports warnings within threshold."""
    if max_warnings is None:
        max_warnings = int(variable_or_default("max_cppcheck_warnings", "0"))
    else:
        max_warnings = int(max_warnings)

    c = Check("cppcheck-clean", "Ensures cppcheck warnings are within threshold", node=node)
    with c:
        cpp = c.get_node(".lang.cpp")
        if not cpp.exists():
            c.skip("Not a C/C++ project")
        project_exists_node = cpp.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No C/C++ project detected in this component")

        lint_node = cpp.get_node(".lint")
        if not lint_node.exists():
            c.skip("cppcheck data not available - ensure cpp collector has run")

        warnings_node = lint_node.get_node(".warnings")
        if warnings_node.exists() and warnings_node.get_value():
            warning_count = len(warnings_node.get_value())
        else:
            warning_count = 0

        c.assert_less_or_equal(
            warning_count,
            max_warnings,
            f"Found {warning_count} cppcheck warning(s), maximum allowed is {max_warnings}. "
            f"Run 'cppcheck --enable=all .' and fix the reported issues."
        )

    return c


if __name__ == "__main__":
    cppcheck_clean()
