"""Require Terraform providers to specify version constraints."""

from lunar_policy import Check
from helpers import get_providers


def main(node=None):
    c = Check("provider-versions-pinned", "Terraform providers have version constraints", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        providers = get_providers(native)
        if not providers:
            c.skip("No providers found in required_providers")

        unpinned = [p["name"] for p in providers if not p["is_pinned"]]
        if unpinned:
            c.fail(
                f"Providers without version constraints: {', '.join(unpinned)}. "
                "Add version constraints in required_providers to ensure reproducible deployments."
            )
    return c


if __name__ == "__main__":
    main()
