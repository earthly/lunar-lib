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
        if required_langs:
            detected_langs = []
            for lang in required_langs:
                if c.exists(f".lang.{lang}"):
                    detected_langs.append(lang)
            
            if not detected_langs:
                c.skip(f"No project detected for required languages: {required_langs}")
                return c
        
        # First check if we have test execution data at all
        if not c.exists(".testing"):
            c.skip("No test execution data found")
            return c

        # Check if pass/fail data is available
        if not c.exists(".testing.all_passing"):
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
