from lunar_policy import Check, variable_or_default


def check_executed(node=None):
    """Check that tests were executed in CI.
    
    Args:
        node: Optional Node for testing. If None, loads from environment.
    
    Returns:
        Check object with result.
    """
    c = Check("executed", "Ensures tests were executed in CI", node=node)
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
        
        c.assert_exists(
            ".testing",
            "No test execution data found. Ensure tests are configured to run in CI."
        )
    return c


if __name__ == "__main__":
    check_executed()
