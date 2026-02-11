from lunar_policy import Check, variable_or_default


def check_coverage_collected(node=None):
    """Check that coverage data is being collected.
    
    Args:
        node: Optional Node for testing. If None, loads from environment.
    
    Returns:
        Check object with result.
    """
    c = Check("coverage-collected", "Coverage data should be collected in CI", node=node)
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
        
        c.assert_exists(
            ".testing.coverage",
            "Coverage data not collected in CI. Configure a coverage tool to run in your CI pipeline."
        )
    return c


if __name__ == "__main__":
    check_coverage_collected()
