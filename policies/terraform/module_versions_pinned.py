"""Require Terraform modules to use pinned versions."""

from lunar_policy import Check
from helpers import get_modules


def main(node=None):
    c = Check("module-versions-pinned", "Terraform modules have pinned versions", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        modules = get_modules(native)
        if not modules:
            c.skip("No modules found")

        unpinned = [m["name"] for m in modules if not m["is_pinned"]]
        if unpinned:
            c.fail(
                f"Modules without pinned versions: {', '.join(unpinned)}. "
                "Add version constraints or use ?ref= to pin module sources."
            )
    return c


if __name__ == "__main__":
    main()
