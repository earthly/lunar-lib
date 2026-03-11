from lunar_policy import Check


def check_phpunit_configured(node=None):
    """Check that PHPUnit is configured for testing."""
    c = Check("phpunit-configured", "Ensures PHPUnit testing is configured", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")

        phpunit = php.get_node(".phpunit_configured")
        if not phpunit.exists():
            c.skip("PHP project data not available - ensure php collector has run")

        c.assert_true(
            phpunit.get_value(),
            "PHPUnit is not configured. Create a phpunit.xml or phpunit.xml.dist "
            "file and add phpunit/phpunit to require-dev in composer.json."
        )
    return c


if __name__ == "__main__":
    check_phpunit_configured()
