from lunar_policy import Check

with Check("go-license-isc", "Disallows ISC Licensed Dependencies") as c:
    # Check direct dependencies
    if c.exists(".lang.go.deps.dependencies.direct"):
        direct_deps = c.get_node(".lang.go.deps.dependencies.direct")
        for dep in direct_deps:
            license_val = dep.get_value_or_default(".license", "")
            if license_val == "ISC":
                dep_path = dep.get_value_or_default(".path", "<unknown>")
                c.assert_true(
                    False,
                    f"Direct dependency '{dep_path}' uses ISC license which is not allowed"
                )
    
    # Check transitive dependencies
    if c.exists(".lang.go.deps.dependencies.transitive"):
        transitive_deps = c.get_node(".lang.go.deps.dependencies.transitive")
        for dep in transitive_deps:
            license_val = dep.get_value_or_default(".license", "")
            if license_val == "ISC":
                dep_path = dep.get_value_or_default(".path", "<unknown>")
                c.assert_true(
                    False,
                    f"Transitive dependency '{dep_path}' uses ISC license which is not allowed"
                )
    
    # If no dependencies found or no ISC licenses found, pass
    c.assert_true(True, "No ISC licensed dependencies found")

