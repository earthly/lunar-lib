from lunar_policy import Check


def check_linter_configured(node=None):
    """Check that a Python linter is configured."""
    c = Check("linter-configured", "Ensures a linter is configured", node=node)
    with c:
        python = c.get_node(".lang.python")
        if not python.exists():
            c.skip("Not a Python project")

        native = python.get_node(".native")
        if not native.exists():
            c.skip("Python project data not available - ensure python collector has run")

        # linter is null when no linter detected, string when detected
        linter_node = native.get_node(".linter")
        linter = linter_node.get_value() if linter_node.exists() else None
        c.assert_true(
            linter is not None and linter != "",
            "No Python linter configured. Set up one of:\n"
            "  - Ruff: add [tool.ruff] to pyproject.toml or create .ruff.toml\n"
            "  - Flake8: create .flake8 or add [flake8] to setup.cfg\n"
            "  - Pylint: create .pylintrc"
        )
    return c


if __name__ == "__main__":
    check_linter_configured()
