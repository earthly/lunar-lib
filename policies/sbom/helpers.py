"""Shared helpers for SBOM policy checks."""


def get_sbom_components(c):
    """Collect SBOM components from both auto and cicd paths.

    Returns a list of component nodes, or an empty list if no SBOM data exists.
    Also returns a boolean indicating whether any SBOM data was found.
    """
    components = []
    has_sbom = False

    for prefix in [".sbom.auto", ".sbom.cicd"]:
        node = c.get_node(prefix)
        if not node.exists():
            continue
        has_sbom = True
        cyclonedx = node.get_node(".cyclonedx.components")
        if cyclonedx.exists():
            for component in cyclonedx:
                components.append(component)
        spdx = node.get_node(".spdx.packages")
        if spdx.exists():
            for component in spdx:
                components.append(component)

    return components, has_sbom


def get_sbom_formats(c):
    """Detect which SBOM formats are present.

    Returns a list of format strings (e.g. ["cyclonedx", "spdx"]).
    """
    formats = []

    for prefix in [".sbom.auto", ".sbom.cicd"]:
        node = c.get_node(prefix)
        if not node.exists():
            continue
        if node.get_node(".cyclonedx").exists():
            if "cyclonedx" not in formats:
                formats.append("cyclonedx")
        if node.get_node(".spdx").exists():
            if "spdx" not in formats:
                formats.append("spdx")

    return formats
