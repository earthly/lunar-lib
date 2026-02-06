import sys
sys.path.insert(0, ".")
from helpers import get_sbom_components
from lunar_policy import Check, variable_or_default

with Check("min-components", "Verifies the SBOM contains a minimum number of components") as c:
    min_count = int(variable_or_default("min_components", "1"))

    components, has_sbom = get_sbom_components(c)
    if not has_sbom:
        c.skip("No SBOM data available")

    total = len(components)
    c.assert_greater_or_equal(
        total,
        min_count,
        f"SBOM contains {total} components, minimum required is {min_count}"
    )
