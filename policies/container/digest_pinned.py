"""Check that container definitions pin base images by digest."""

from lunar_policy import Check
from helpers import image_digest


def main(node=None):
    c = Check(
        "digest-pinned",
        "Container definitions should pin base images by digest",
        node=node,
    )
    with c:
        definitions = c.get_node(".containers.definitions")
        if not definitions.exists():
            c.skip("No Dockerfiles found in this component")

        for definition in definitions:
            if not definition.get_value_or_default(".valid", False):
                continue

            path = definition.get_value(".path")
            base_images = definition.get_node(".base_images")

            if not base_images.exists():
                continue

            for img in base_images:
                reference = img.get_value(".reference")
                image = img.get_value_or_default(".image", reference)

                # Skip scratch image
                if image == "scratch":
                    continue

                if not image_digest(reference):
                    c.fail(
                        f"'{path}' uses '{reference}' without a digest. "
                        f"Pin it by digest (e.g., node:20@sha256:...)"
                    )
    return c


if __name__ == "__main__":
    main()
