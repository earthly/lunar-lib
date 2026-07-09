from lunar_policy import Check


def check_linter_configured(node=None):
    """Check that a Kotlin static-analysis / formatting tool is configured."""
    c = Check(
        "linter-configured",
        "Ensures detekt or ktlint is configured",
        node=node,
    )
    with c:
        kotlin = c.get_node(".lang.kotlin")
        if not kotlin.exists():
            c.skip("Not a Kotlin project")
        project_exists_node = kotlin.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Kotlin project detected in this component")

        detekt_node = kotlin.get_node(".detekt_configured")
        ktlint_node = kotlin.get_node(".ktlint_configured")

        has_detekt = detekt_node.get_value() if detekt_node.exists() else False
        has_ktlint = ktlint_node.get_value() if ktlint_node.exists() else False

        c.assert_true(
            has_detekt or has_ktlint,
            "No Kotlin linter configured. Add detekt (detekt.yml + the detekt "
            "Gradle plugin) or ktlint for consistent code quality and formatting.",
        )
    return c


if __name__ == "__main__":
    check_linter_configured()
