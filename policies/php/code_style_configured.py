from lunar_policy import Check


def check_code_style_configured(node=None):
    """Check that a code style tool (PHP-CS-Fixer or PHP_CodeSniffer) is configured."""
    c = Check("code-style-configured", "Ensures code style tool is configured", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")
        project_exists_node = php.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No PHP project detected in this component")

        cs_node = php.get_node(".code_style_configured")
        if not cs_node.exists():
            c.skip("Code style data not available - ensure php collector has run")

        c.assert_true(
            cs_node.get_value(),
            "No code style tool configured. Add PHP-CS-Fixer or PHP_CodeSniffer to your project."
        )
    return c


if __name__ == "__main__":
    check_code_style_configured()
