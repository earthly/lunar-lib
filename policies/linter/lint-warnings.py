from lunar_policy import Check, variable_or_default

with Check("max-warnings", "Ensures lint warnings are at or below the maximum allowed") as c:
    language = variable_or_default("language", "")
    max_warnings_str = variable_or_default("max_warnings", "0")
    
    # Validate required input
    if not language:
        raise ValueError(
            "Policy misconfiguration: 'language' must be specified. "
            "Set this to the programming language to check (e.g., 'go', 'java', 'python')."
        )
    
    # Parse max_warnings
    try:
        max_warnings = int(max_warnings_str)
    except ValueError:
        raise ValueError(
            f"Policy misconfiguration: 'max_warnings' must be an integer, got '{max_warnings_str}'"
        )
    
    # Skip if this language is not present in the component
    lang_node = c.get_node(f".lang.{language}")
    if not lang_node.exists():
        c.skip(f"No {language} code detected in this component")
    
    # Check for lint warnings
    lint_path = f".lang.{language}.lint"
    warnings_path = f"{lint_path}.warnings"
    
    # Use assert_exists to handle pending vs missing correctly
    c.assert_exists(lint_path, f"No linting data found for {language}")
    
    warnings = c.get_node(warnings_path)
    if warnings.exists():
        warning_count = len(list(warnings))
        c.assert_less_or_equal(
            warning_count,
            max_warnings,
            f"Found {warning_count} lint warning(s), maximum allowed is {max_warnings}"
        )
    # If lint data exists but no warnings array - treat as 0 warnings (pass)
