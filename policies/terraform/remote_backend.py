"""Require Terraform to use a remote backend for state management."""

from lunar_policy import Check, variable_or_default
from helpers import get_backend


def main(node=None):
    c = Check("remote-backend", "Terraform uses a remote backend", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        backend = get_backend(native)
        if backend is None:
            c.fail(
                "No backend configured. Terraform state is stored locally, "
                "which is fragile and cannot be shared across teams."
            )
            return c

        approved_str = variable_or_default("required_backend_types", "")
        if approved_str:
            approved = [t.strip() for t in approved_str.split(",") if t.strip()]
            if backend["type"] not in approved:
                c.fail(
                    f"Backend type '{backend['type']}' is not in approved list: "
                    f"{', '.join(approved)}"
                )
    return c


if __name__ == "__main__":
    main()
