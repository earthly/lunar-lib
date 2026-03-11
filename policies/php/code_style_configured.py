from lunar_policy import Check


def check_code_style_configured(node=None):
    """Check that a code style tool (PHP-CS-Fixer or PHP_CodeSniffer) is configured."""
    c = Check("code-style-configured", "Ensures code style enforcement is configured", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")

        cs = php.get_node(".code_style_configured")
        if not cs.exists():
            c.skip("PHP project data not available - ensure php collector has run")

        c.assert_true(
            cs.get_value(),
            "No code style tool configured. Set up one of:\n"
            "  - PHP-CS-Fixer: create .php-cs-fixer.php and add friendsofphp/php-cs-fixer to require-dev\n"
            "  - PHP_CodeSniffer: create phpcs.xml and add squizlabs/php_codesniffer to require-dev"
        )
    return c


if __name__ == "__main__":
    check_code_style_configured()
