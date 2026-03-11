from lunar_policy import Check


def check_static_analysis_configured(node=None):
    """Check that a static analysis tool (PHPStan or Psalm) is configured."""
    c = Check("static-analysis-configured", "Ensures static analysis is configured", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")

        sa = php.get_node(".static_analysis_configured")
        if not sa.exists():
            c.skip("PHP project data not available - ensure php collector has run")

        c.assert_true(
            sa.get_value(),
            "No static analysis tool configured. Set up one of:\n"
            "  - PHPStan: create phpstan.neon and add phpstan/phpstan to require-dev\n"
            "  - Psalm: create psalm.xml and add vimeo/psalm to require-dev"
        )
    return c


if __name__ == "__main__":
    check_static_analysis_configured()
