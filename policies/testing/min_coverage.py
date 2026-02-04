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
        
        # If required_languages is set, check if component has any matching language project
        if required_langs:
            detected_langs = []
            for lang in required_langs:
                if c.get_node(f".lang.{lang}").exists():
                    detected_langs.append(lang)
            
            if not detected_langs:
                c.skip(f"No project detected for required languages: {required_langs}")
                return c
        
        # Check if coverage data exists first
        if not c.get_node(".testing.coverage").exists():
            c.skip("No coverage data available")
            return c
        
        # Check if percentage is reported
        if not c.get_node(".testing.coverage.percentage").exists():
            c.skip("Coverage percentage not reported")
            return c
        
        min_coverage = int(variable_or_default("min_coverage", "80"))
        coverage = c.get_value(".testing.coverage.percentage")
        c.assert_greater_or_equal(
            coverage,
            min_coverage,
            f"Coverage {coverage}% is below minimum {min_coverage}%"
        )
    return c


if __name__ == "__main__":
    check_min_coverage()
