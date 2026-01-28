from lunar_policy import Check, variable_or_default

with Check("ran", "Ensures linting was executed") as c:
    language = variable_or_default("language", "")
    
    # Validate required input
    if not language:
        raise ValueError(
            "Policy misconfiguration: 'language' must be specified. "
            "Set this to the programming language to check (e.g., 'go', 'java', 'python')."
        )
    
    # Skip if this language is not present in the component
    lang_node = c.get_node(f".lang.{language}")
    if not lang_node.exists():
        c.skip(f"No {language} code detected in this component")
    
    # Check that lint data exists
    lint_path = f".lang.{language}.lint"
    
    c.assert_exists(
        lint_path,
        f"No linting data found for {language}. "
        f"Ensure a linter is configured to run (e.g., golangci-lint for Go)."
    )
