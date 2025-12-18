from lunar_policy import Check, variable_or_default

with Check("disallowed-licenses", "Disallows Specified Licenses in Dependencies") as c:
    # Get disallowed licenses from input (comma-separated)
    disallowed_str = variable_or_default("licenses", "ISC")
    disallowed_licenses = [license.strip().upper() for license in disallowed_str.split(",") if license.strip()]
    
    if not disallowed_licenses:
        c.assert_true(True, "No disallowed licenses configured")
    else:
        # Check all languages under .lang.*
        if c.exists(".lang"):
            lang_node = c.get_node(".lang")
            
            # Iterate through each language (go, python, nodejs, etc.)
            for lang_name in lang_node:
                # Check for dependencies structure: .lang.<lang>.dependencies
                deps_path = f".lang.{lang_name}.dependencies"
                if c.exists(deps_path):
                    deps_node = c.get_node(deps_path)
                    
                    # Check direct dependencies
                    if deps_node.exists(".direct"):
                        direct_deps = deps_node.get_node(".direct")
                        for dep in direct_deps:
                            license_val = dep.get_value_or_default(".license", "")
                            # Skip if no license (collector may not support license collection)
                            if license_val:
                                license_val = license_val.upper()
                                if license_val in disallowed_licenses:
                                    dep_path = dep.get_value_or_default(".path", "<unknown>")
                                    c.assert_true(
                                        False,
                                        f"Direct dependency '{dep_path}' in {lang_name} uses {license_val} license which is not allowed"
                                    )
                    
                    # Check transitive dependencies
                    if deps_node.exists(".transitive"):
                        transitive_deps = deps_node.get_node(".transitive")
                        for dep in transitive_deps:
                            license_val = dep.get_value_or_default(".license", "")
                            # Skip if no license (collector may not support license collection)
                            if license_val:
                                license_val = license_val.upper()
                                if license_val in disallowed_licenses:
                                    dep_path = dep.get_value_or_default(".path", "<unknown>")
                                    c.assert_true(
                                        False,
                                        f"Transitive dependency '{dep_path}' in {lang_name} uses {license_val} license which is not allowed"
                                    )
        
        # If we get here without any failures, all licenses are allowed
        c.assert_true(True, f"No disallowed licenses ({', '.join(disallowed_licenses)}) found in dependencies")

