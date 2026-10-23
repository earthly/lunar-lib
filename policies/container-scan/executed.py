"""Verify container image scanning was executed."""

from helpers import no_scan_data_reasons, pushed_image_refs
from lunar_policy import Check


def main(node=None):
    c = Check("executed", "Container scan must be executed", node=node)
    with c:
        containers = c.get_node(".containers")
        if not containers.exists():
            c.skip("No container definitions detected in this component")

        if not c.get_node(".container_scan").exists():
            for reason in no_scan_data_reasons(pushed_image_refs(containers)):
                c.fail(reason)
    return c


if __name__ == "__main__":
    main()
