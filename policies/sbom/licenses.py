import re
import sys
from lunar_policy import Check, variable_or_default

with Check("sbom-disallowed-licenses", "Disallows Specified Licenses in SBOM Components") as c:
    # Get disallowed licenses from input (comma-separated regex patterns)
    disallowed_str = variable_or_default("disallowed_licenses", "")
    disallowed_patterns = [pattern.strip() for pattern in disallowed_str.split(",") if pattern.strip()]
    
    if not disallowed_patterns:
        c.assert_true(True, "No disallowed licenses configured")
    else:
        # Compile regex patterns
        regex_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in disallowed_patterns]
        
        # Check SBOM components under .sbom.cyclonedx.components
        components = c.get_node(".sbom.cyclonedx.components")
        if components.exists():
            for component in components:
                component_name = component.get_value_or_default(".name", "<unknown>")
                licenses = component.get_node(".licenses")
                if not licenses.exists():
                    print(f"Warning: Component '{component_name}' has no license information", file=sys.stderr)
                    continue
                for license_entry in licenses:
                    license_obj = license_entry.get_node(".license")
                    if not license_obj.exists():
                        print(f"Warning: Component '{component_name}' has license information but no license object", file=sys.stderr)
                        continue
                    license_id = license_obj.get_value_or_default(".id", "<unknown>")
                    
                    # Check if license matches any disallowed pattern
                    for pattern in regex_patterns:
                        if pattern.search(license_id):
                            c.fail(f"Component '{component_name}' uses {license_id} license which matches disallowed pattern")
                            break