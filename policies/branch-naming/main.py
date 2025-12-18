from lunar_policy import Check, variable_or_default

with Check("branch-naming-convention", "Branches must start with an approved prefix") as c:
    is_pr = c.get_node(".github.is_pr")
    
    # Only check branch naming for PRs, skip on main branch
    if not is_pr.exists() or not is_pr.get_value_or_default(".", False):
        c.assert_true(True, "Skipped on main branch (only runs on PRs)")
    else:
        pr_data = c.get_node(".github.pr")
        if pr_data.exists():
            branch_name = pr_data.get_value_or_default(".head.ref", "")
            if branch_name:
                # Get approved prefixes from policy configuration
                approved_prefixes_str = variable_or_default("approvedPrefixes", "feature/,bugfix/,hotfix/,release/,f/,b/,h/")
                # Split by comma and strip whitespace
                approved_prefixes = [p.strip() for p in approved_prefixes_str.split(",") if p.strip()]
                
                # Check if branch starts with any approved prefix
                starts_with_approved = any(branch_name.startswith(prefix) for prefix in approved_prefixes)
                
                if not starts_with_approved:
                    prefixes_list = ", ".join(approved_prefixes)
                    c.fail(f"Branch '{branch_name}' must start with one of the approved prefixes: {prefixes_list}")

