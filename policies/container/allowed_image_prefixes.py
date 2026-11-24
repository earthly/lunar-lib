"""Check that base images come from allowed image path prefixes."""

import re

from lunar_policy import Check, variable_or_default
from helpers import image_repository


def parse_prefixes(value):
    """Split the input on commas and whitespace; each entry must start with a registry host."""
    prefixes = []
    for entry in re.split(r"[\s,]+", value or ""):
        prefix = entry.rstrip("/").lower()
        if not prefix:
            continue
        host = prefix.split("/", 1)[0]
        if not ("." in host or ":" in host or host == "localhost"):
            raise ValueError(
                f"Policy misconfiguration: allowed_image_prefixes entry '{entry}' must start "
                "with a registry host, e.g. 'registry.example.com/team' or 'docker.io/library'."
            )
        prefixes.append(prefix)
    return prefixes


def is_under(repository, prefix):
    """Match whole path segments, so 'reg/team' doesn't match 'reg/team-other/app'."""
    return repository == prefix or repository.startswith(prefix + "/")


def main(node=None):
    c = Check(
        "allowed-image-prefixes",
        "Base images should come from allowed image path prefixes",
        node=node,
    )
    with c:
        prefixes = parse_prefixes(variable_or_default("allowed_image_prefixes", ""))
        if not prefixes:
            c.skip(
                "No allowed image prefixes configured. Set the `allowed_image_prefixes` "
                "variable to enforce this check."
            )

        definitions = c.get_node(".containers.definitions")
        if not definitions.exists():
            c.skip("No Dockerfiles found in this component")

        checked = 0
        for definition in definitions:
            if not definition.get_value_or_default(".valid", False):
                continue

            path = definition.get_value(".path")
            base_images = definition.get_node(".base_images")
            if not base_images.exists():
                continue

            for img in base_images:
                reference = img.get_value(".reference")
                checked += 1
                if reference == "scratch":
                    continue
                if not any(is_under(image_repository(reference), p) for p in prefixes):
                    c.fail(
                        f"'{path}' uses image '{reference}', which is not under an "
                        f"allowed prefix: {', '.join(prefixes)}"
                    )

        if checked == 0:
            c.skip(
                "No base image could be read from this component's Dockerfiles. "
                "Images supplied at build time, such as FROM ${BASE} with no ARG default, "
                "aren't recorded, so there is nothing to check."
            )
    return c


if __name__ == "__main__":
    main()
