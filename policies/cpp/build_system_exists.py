from lunar_policy import Check, variable_or_default


def build_system_exists(node=None):
    """Ensures at least one C/C++ build system is detected."""
    c = Check("build-system-exists", "Ensures a C/C++ build system is present", node=node)
    with c:
        cpp = c.get_node(".lang.cpp")
        if not cpp.exists():
            c.skip("Not a C/C++ project")

        bs_node = cpp.get_node(".build_systems")
        if not bs_node.exists():
            c.skip("Build system data not available - ensure cpp collector has run")

        build_systems = bs_node.get_value()
        c.assert_true(
            isinstance(build_systems, list) and len(build_systems) > 0,
            "No build system detected. C/C++ projects need CMake, Make, Meson, or another build system."
        )

    return c


if __name__ == "__main__":
    build_system_exists()
