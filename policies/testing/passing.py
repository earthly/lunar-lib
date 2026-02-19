from lunar_policy import Check, variable_or_default


def check_passing(node=None):
    """Check that all tests pass.
    
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
        
        # Check if component has a language project
        # Use get_node().exists() to get a boolean without raising NoDataError
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
        
        # Use exists() to check for test pass/fail data:
        # - Before collectors finish: exists() raises NoDataError -> pending
        # - After collectors finish, no data: exists() returns False -> fail
        # - After collectors finish, has data: exists() returns True -> use real value
        n = c.get_node(".testing.all_passing")
        if n.exists():
            c.assert_true(
                n.get_value(),
                "Tests are failing. Check CI logs for test failure details."
            )
        else:
            c.fail("Test pass/fail data not available. Configure your test runner to report results.")
    return c


if __name__ == "__main__":
    check_passing()
