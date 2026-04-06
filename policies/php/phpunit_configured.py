from lunar_policy import Check


def check_phpunit_configured(node=None):
    """Check that PHPUnit is configured for the PHP project."""
    c = Check("phpunit-configured", "Ensures PHPUnit test framework is configured", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")
        project_exists_node = php.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No PHP project detected in this component")

        phpunit_node = php.get_node(".phpunit_configured")
        if not phpunit_node.exists():
            c.skip("PHPUnit configuration data not available - ensure php collector has run")

        c.assert_true(
            phpunit_node.get_value(),
            "PHPUnit not configured. Add phpunit/phpunit to require-dev and create phpunit.xml."
        )
    return c


if __name__ == "__main__":
    check_phpunit_configured()
