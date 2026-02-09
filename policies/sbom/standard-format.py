import sys
sys.path.insert(0, ".")
from helpers import get_sbom_formats
from lunar_policy import Check, variable_or_default

with Check("standard-format", "Validates the SBOM uses an approved format") as c:
    allowed_str = variable_or_default("allowed_formats", "")
    allowed = [f.strip().lower() for f in allowed_str.split(",") if f.strip()]

    if not allowed:
        # No restriction configured — auto-pass
        pass
    else:
        formats = get_sbom_formats(c)
        if not formats:
            c.skip("No SBOM data available")

        for fmt in formats:
            c.assert_true(
                fmt in allowed,
                f"SBOM format '{fmt}' is not in allowed formats: {', '.join(allowed)}"
            )
