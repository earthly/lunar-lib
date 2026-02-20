"""Ensure stateful resources have lifecycle { prevent_destroy = true }."""

from lunar_policy import Check
from helpers import get_modules, get_unprotected


def main(node=None):
    c = Check("datastore-destroy-protection", "Stateful resources have destroy protection", node=node)
    with c:
        modules = get_modules(c)

        total_datastores = 0
        for mod in modules:
            path = mod.get_value_or_default(".path", ".")
            unprotected = get_unprotected(mod, "datastore")
            resources = mod.get_node(".resources")
            if resources.exists():
                total_datastores += sum(
                    1 for r in resources
                    if r.get_value_or_default(".category", "") == "datastore"
                )
            if unprotected:
                c.fail(f"Module '{path}': stateful resources without destroy protection: {', '.join(unprotected)}")

        if total_datastores == 0:
            c.skip("No datastore resources found")
    return c


if __name__ == "__main__":
    main()
