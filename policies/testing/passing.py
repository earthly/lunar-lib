from lunar_policy import Check, variable_or_default


def check_passing(node=None):
    """Check that all tests pass.
    
    Skips if pass/fail data is not available (some collectors only 
    report execution, not results).
    
    Args:
        node: Optional Node for testing. If None, loads from environment.
    
    Returns:
        Check object with result.
    """
    c = Check("passing", "Ensures all tests pass", node=node)
    with c:
        # Get required languages from input
        required_langs_str = variable_or_default("required_languages", "")
        required_langs = [lang.strip() for lang in required_langs_str.split(",") if lang.strip()]
        
        # If required_languages is set, check if component has any matching language project
        # Use get_node().exists() to get a boolean without raising NoDataError
        if required_langs:
            detected_langs = []
            for lang in required_langs:
                if c.get_node(f".lang.{lang}").exists():
                    detected_langs.append(lang)
            
            if not detected_langs:
                c.skip(f"No project detected for required languages: {', '.join(required_langs)}")
                return c
        
        # Check if we have test execution data at all
        # get_node().exists() returns False without raising NoDataError
        testing_node = c.get_node(".testing")
        if not testing_node.exists():
            c.skip("No test execution data found")
            return c

        # Check if pass/fail data is available
        all_passing_node = c.get_node(".testing.all_passing")
        if not all_passing_node.exists():
            c.skip(
                "Test pass/fail data not available. "
                "This requires a collector that reports detailed test results."
            )
            return c

        # Assert tests are passing
        c.assert_true(
            c.get_value(".testing.all_passing"),
            "Tests are failing. Check CI logs for test failure details."
        )
    return c


if __name__ == "__main__":
    check_passing()
