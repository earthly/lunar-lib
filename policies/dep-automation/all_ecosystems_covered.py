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


def _bool_true(c, path):
    """True if path exists AND its value is truthy (for boolean flags)."""
    node = c.get_node(path)
    if not node.exists():
        return False
    return bool(node.get_value())


def _path_present(c, path):
    """True if path exists in the data (for presence/detection)."""
    return c.get_node(path).exists()


def _detect_required_ecosystems(c):
    required = set()
    for path, ecosystem in ECOSYSTEM_MAP:
        if _path_present(c, path):
            required.add(ecosystem)

    # Java: require matching build tool ecosystem (maven or gradle)
    if _path_present(c, ".lang.java"):
        build_tool_node = c.get_node(".lang.java.build_tool")
        if build_tool_node.exists():
            build_tool = build_tool_node.get_value()
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
        dependabot_exists = _bool_true(c, ".dep_automation.dependabot.exists")
        renovate_exists = _bool_true(c, ".dep_automation.renovate.exists")

        if not dependabot_exists and not renovate_exists:
            c.skip(
                "No dependency update tool configured "
                "(dep-update-tool-configured covers this case)"
            )

        # Renovate with all managers enabled covers every ecosystem by default
        renovate_covers_all = False
        if renovate_exists:
            all_managers_node = c.get_node(
                ".dep_automation.renovate.all_managers_enabled"
            )
            if all_managers_node.exists() and all_managers_node.get_value():
                renovate_covers_all = True

        if not renovate_covers_all:
            covered = set()
            if dependabot_exists:
                eco_node = c.get_node(".dep_automation.dependabot.ecosystems")
                if eco_node.exists():
                    val = eco_node.get_value()
                    if isinstance(val, list):
                        covered.update(val)
            if renovate_exists:
                mgr_node = c.get_node(".dep_automation.renovate.enabled_managers")
                if mgr_node.exists():
                    val = mgr_node.get_value()
                    if isinstance(val, list):
                        covered.update(val)

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
