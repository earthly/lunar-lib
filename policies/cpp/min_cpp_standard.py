from lunar_policy import Check, variable_or_default


def min_cpp_standard(min_standard=None, node=None):
    """Ensures C++ standard meets the minimum requirement."""
    if min_standard is None:
        min_standard = variable_or_default("min_cpp_standard", "17")

    c = Check("min-cpp-standard", "Ensures minimum C++ standard version", node=node)
    with c:
        cpp = c.get_node(".lang.cpp")
        if not cpp.exists():
            c.skip("Not a C/C++ project")

        std_node = cpp.get_node(".cpp_standard")
        if not std_node.exists():
            c.skip("C++ standard not detected - check CMAKE_CXX_STANDARD or compiler flags")

        actual = std_node.get_value()
        try:
            actual_int = int(str(actual))
            min_int = int(str(min_standard))
            c.assert_true(
                actual_int >= min_int,
                f"C++ standard {actual} is below minimum {min_standard}. "
                f"Update CMAKE_CXX_STANDARD or compiler flags to use C++{min_standard} or later."
            )
        except (ValueError, TypeError):
            c.fail(f"Could not parse C++ standard: '{actual}'")

    return c


if __name__ == "__main__":
    min_cpp_standard()
