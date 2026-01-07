from lunar_policy import Check, variable_or_default

with Check("readme-required-sections", "README.md should contain required sections") as c:
    readme = c.get_node(".repo.readme")
    
    if not readme.exists():
        c.skip()
    
    # Skip if no required sections are configured
    required_sections_str = variable_or_default("required_sections", "")
    if not required_sections_str:
        c.skip()

    # Prase comma-separated list of required sections from input
    required_sections = [section.strip() for section in required_sections_str.split(",") if section.strip()]
    
    # Convert readme sections to set for case-insensitive comparison
    sections = readme.get_value_or_default(".sections", [])
    sections_lower = [s.lower() for s in sections]
    required_sections_lower = [s.lower() for s in required_sections]
    
    missing_sections = []
    for required in required_sections_lower:
        if required not in sections_lower:
            # Find the original case version
            original_required = required_sections[required_sections_lower.index(required)]
            missing_sections.append(original_required)
    
    if missing_sections:
        c.fail(f"README.md is missing required sections: {', '.join(missing_sections)}")

