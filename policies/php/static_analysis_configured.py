from lunar_policy import Check


def check_static_analysis_configured(node=None):
    """Check that a static analysis tool (PHPStan or Psalm) is configured."""
    c = Check("static-analysis-configured", "Ensures static analysis tool is configured", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")
        if not php.get_node(".project_exists").exists():
            c.skip("No PHP project detected in this component")

        sa_node = php.get_node(".static_analysis_configured")
        if not sa_node.exists():
            c.skip("Static analysis data not available - ensure php collector has run")

        c.assert_true(
            sa_node.get_value(),
            "No static analysis tool configured. Add PHPStan or Psalm to your project."
        )
    return c


if __name__ == "__main__":
    check_static_analysis_configured()
