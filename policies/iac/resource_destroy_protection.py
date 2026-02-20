"""Ensure stateless infrastructure resources have lifecycle { prevent_destroy = true }."""

from lunar_policy import Check
from helpers import get_modules, get_unprotected


def main(node=None):
    c = Check("resource-destroy-protection", "Stateless resources have destroy protection", node=node)
    with c:
        modules = get_modules(c)

        total_compute = 0
        for mod in modules:
            path = mod.get_value_or_default(".path", ".")
            unprotected = get_unprotected(mod, "compute")
            unprotected += get_unprotected(mod, "network")
            resources = mod.get_node(".resources")
            if resources.exists():
                total_compute += sum(
                    1 for r in resources
                    if r.get_value_or_default(".category", "") in ("compute", "network")
                )
            if unprotected:
                c.fail(f"Module '{path}': stateless resources without destroy protection: {', '.join(unprotected)}")

        if total_compute == 0:
            c.skip("No stateless infrastructure resources found")
    return c


if __name__ == "__main__":
    main()
