import sys
sys.path.insert(0, ".")
from helpers import get_sbom_components
from lunar_policy import Check, variable_or_default

with Check("has-licenses", "Verifies SBOM components have license information") as c:
    min_coverage = int(variable_or_default("min_license_coverage", "90"))

    components, has_sbom = get_sbom_components(c)
    if not has_sbom:
        c.skip("No SBOM data available")

    total = len(components)
    if total == 0:
        c.skip("SBOM has no components")

    with_license = 0
    for component in components:
        licenses = component.get_node(".licenses")
        if licenses.exists():
            with_license += 1

    coverage = (with_license / total) * 100
    c.assert_greater_or_equal(
        coverage,
        min_coverage,
        f"License coverage {coverage:.0f}% is below minimum {min_coverage}% "
        f"({with_license}/{total} components have license info)"
    )
