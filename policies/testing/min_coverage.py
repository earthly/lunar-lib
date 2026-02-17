from lunar_policy import Check, variable_or_default


def check_min_coverage(node=None):
    """Check that code coverage meets minimum threshold.
    
    Args:
        node: Optional Node for testing. If None, loads from environment.
    
    Returns:
        Check object with result.
    """
    c = Check("min-coverage", "Coverage should meet minimum threshold", node=node)
    with c:
        # Get required languages from input
        required_langs_str = variable_or_default("required_languages", "")
        required_langs = [lang.strip() for lang in required_langs_str.split(",") if lang.strip()]
        
        # Check if component has a language project
        if required_langs:
            # Check for specific languages
            detected_langs = []
            for lang in required_langs:
                if c.get_node(f".lang.{lang}").exists():
                    detected_langs.append(lang)
            
            if not detected_langs:
                c.skip(f"No project detected for required languages: {', '.join(required_langs)}")
        else:
            # No specific languages required - check if ANY language project exists
            if not c.get_node(".lang").exists():
                c.skip("No language project detected")
        
        # Assert coverage data exists - fail (not skip) if missing
        # This ensures the score correctly reflects missing coverage
        c.assert_exists(
            ".testing.coverage",
            "No coverage data collected. Configure a coverage tool to run in your CI pipeline."
        )

        # Only check percentage if coverage data exists (avoid ValueError)
        if c.get_node(".testing.coverage").exists():
            c.assert_exists(
                ".testing.coverage.percentage",
                "Coverage percentage not reported. Ensure your coverage tool reports metrics."
            )
            if c.get_node(".testing.coverage.percentage").exists():
                min_coverage = float(variable_or_default("min_coverage", "80"))
                coverage = c.get_value(".testing.coverage.percentage")
                c.assert_greater_or_equal(
                    coverage,
                    min_coverage,
                    f"Coverage {coverage}% is below minimum {min_coverage}%"
                )
    return c


if __name__ == "__main__":
    check_min_coverage()
