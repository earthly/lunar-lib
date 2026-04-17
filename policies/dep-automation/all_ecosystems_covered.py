from lunar_policy import Check

# Map component signals to Dependabot's package-ecosystem names.
# Scoped to ecosystems with matching lunar-lib collectors — if there's no
# collector that produces the signal, the policy has no way to detect it.
ECOSYSTEM_MAP = [
    (".lang.nodejs", "npm"),
    (".lang.python", "pip"),
    (".lang.go", "gomod"),
    (".lang.ruby", "bundler"),
    (".lang.rust", "cargo"),
    (".lang.dotnet", "nuget"),
    (".lang.php", "composer"),
    (".containers.definitions", "docker"),
    (".ci.native.github_actions", "github-actions"),
    (".iac", "terraform"),
]

# Java is split between maven and gradle — tracked separately below
JAVA_BUILD_ECOSYSTEMS = {"maven", "gradle"}


def _path_present(c, path):
    """True if path exists in the data (for presence/detection)."""
    return c.get_node(path).get_value_or_default(".", None) is not None


def _detect_required_ecosystems(c):
    required = set()
    for path, ecosystem in ECOSYSTEM_MAP:
        if _path_present(c, path):
            required.add(ecosystem)

    # Java: require matching build tool ecosystem (maven or gradle)
    if _path_present(c, ".lang.java"):
        build_tool = (
            c.get_node(".lang.java")
            .get_value_or_default(".build_tool", None)
        )
        if isinstance(build_tool, str) and build_tool in JAVA_BUILD_ECOSYSTEMS:
            required.add(build_tool)
        else:
            required.add("maven")

    return required


def main(node=None):
    c = Check(
        "all-ecosystems-covered",
        "All detected package ecosystems have update rules configured",
        node=node,
    )
    with c:
        dependabot = (
            c.get_node(".dep_automation.dependabot")
            .get_value_or_default(".", None)
        )
        renovate = (
            c.get_node(".dep_automation.renovate")
            .get_value_or_default(".", None)
        )

        if dependabot is None and renovate is None:
            c.skip(
                "No dependency update tool configured "
                "(dep-update-tool-configured covers this case)"
            )
            return c

        # Renovate with all managers enabled covers every ecosystem by default
        renovate_covers_all = bool(
            renovate and renovate.get("all_managers_enabled")
        )

        if not renovate_covers_all:
            covered = set()
            if dependabot:
                eco = dependabot.get("ecosystems")
                if isinstance(eco, list):
                    covered.update(eco)
            if renovate:
                mgrs = renovate.get("enabled_managers")
                if isinstance(mgrs, list):
                    covered.update(mgrs)

            required = _detect_required_ecosystems(c)
            missing = sorted(required - covered)

            if missing:
                c.fail(
                    f"Missing dependency update coverage for: "
                    f"{', '.join(missing)}. Add update entries to Dependabot or "
                    f"configure Renovate."
                )

    return c


if __name__ == "__main__":
    main()
