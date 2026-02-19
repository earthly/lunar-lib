from lunar_policy import Check


def check_linter_configured(node=None):
    """Check that a Python linter is configured."""
    c = Check("linter-configured", "Ensures a linter is configured", node=node)
    with c:
        python = c.get_node(".lang.python")
        if not python.exists():
            c.skip("Not a Python project")

        linter_node = python.get_node(".linter_configured")
        if not linter_node.exists():
            c.skip("Linter data not available - ensure python collector has run")

        c.assert_true(
            linter_node.get_value(),
            "No Python linter configured. Set up one of:\n"
            "  - Ruff: add [tool.ruff] to pyproject.toml or create .ruff.toml\n"
            "  - Flake8: create .flake8 or add [flake8] to setup.cfg\n"
            "  - Pylint: create .pylintrc"
        )
    return c


if __name__ == "__main__":
    check_linter_configured()
