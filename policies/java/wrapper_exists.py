from lunar_policy import Check


def check_wrapper_exists(node=None):
    """Check that a build tool wrapper exists (mvnw or gradlew)."""
    c = Check("wrapper-exists", "Ensures build tool wrapper exists", node=node)
    with c:
        java = c.get_node(".lang.java")
        if not java.exists():
            c.skip("Not a Java project")

        native = java.get_node(".native")
        if not native.exists():
            c.skip("Java native data not available")

        build_systems_node = java.get_node(".build_systems")
        if not build_systems_node.exists():
            c.skip("Build systems not detected")

        build_systems = build_systems_node.get_value()

        # Check wrapper for each detected build system
        missing = []
        if "maven" in build_systems:
            mvnw_node = native.get_node(".mvnw.exists")
            if not mvnw_node.exists() or not mvnw_node.get_value():
                missing.append("mvnw (Maven wrapper)")

        if "gradle" in build_systems:
            gradlew_node = native.get_node(".gradlew.exists")
            if not gradlew_node.exists() or not gradlew_node.get_value():
                missing.append("gradlew (Gradle wrapper)")

        if missing:
            c.fail(
                f"Missing build tool wrapper(s): {', '.join(missing)}. "
                "Wrappers ensure reproducible builds without pre-installed tools."
            )
    return c


if __name__ == "__main__":
    check_wrapper_exists()
