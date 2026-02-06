import re
import sys
sys.path.insert(0, ".")
from helpers import get_sbom_components
from lunar_policy import Check, variable_or_default

with Check("disallowed-licenses", "Checks for disallowed licenses in SBOM components") as c:
    disallowed_str = variable_or_default("disallowed_licenses", "")
    disallowed_patterns = [p.strip() for p in disallowed_str.split(",") if p.strip()]

    if not disallowed_patterns:
        # No patterns configured — auto-pass
        pass
    else:
        regex_patterns = [re.compile(p, re.IGNORECASE) for p in disallowed_patterns]

        components, has_sbom = get_sbom_components(c)
        if not has_sbom:
            c.skip("No SBOM data available")

        for component in components:
            component_name = component.get_value_or_default(".name", "<unknown>")
            licenses = component.get_node(".licenses")
            if not licenses.exists():
                continue
            for license_entry in licenses:
                license_obj = license_entry.get_node(".license")
                if not license_obj.exists():
                    continue
                license_id = license_obj.get_value_or_default(".id", "")
                if not license_id:
                    continue
                for pattern in regex_patterns:
                    if pattern.search(license_id):
                        c.fail(
                            f"Component '{component_name}' uses disallowed license "
                            f"'{license_id}' (matches pattern '{pattern.pattern}')"
                        )
                        break
