"""Ensure stateful resources have lifecycle { prevent_destroy = true }."""

from lunar_policy import Check, variable_or_default
from helpers import check_destroy_protection, DEFAULT_DATASTORE_TYPES


def main(node=None):
    c = Check("datastore-destroy-protection", "Stateful resources have destroy protection", node=node)
    with c:
        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        extra = variable_or_default("extra_datastore_types", "")
        types = list(DEFAULT_DATASTORE_TYPES)
        if extra:
            types.extend(t.strip() for t in extra.split(",") if t.strip())

        count, unprotected = check_destroy_protection(native, set(types))
        if count == 0:
            c.skip("No datastore resources found")

        if unprotected:
            c.fail(f"Stateful resources without destroy protection: {', '.join(unprotected)}")
    return c


if __name__ == "__main__":
    main()
