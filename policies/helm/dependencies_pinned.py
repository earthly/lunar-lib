from lunar_policy import Check


def main(node=None):
    """Chart dependencies must declare a version constraint (not '*' or empty)."""
    c = Check("dependencies-pinned", "Helm chart dependencies should be pinned", node=node)
    with c:
        charts = c.get_node(".k8s.helm.charts")
        if not charts.exists():
            c.skip("No Helm charts found in this repository")

        any_dep = False
        for chart in charts:
            path = chart.get_value_or_default(".path", "<unknown>")
            name = chart.get_value_or_default(".name", "<chart>")

            deps = chart.get_node(".dependencies")
            if not deps.exists():
                continue

            for dep in deps:
                any_dep = True
                dep_name = dep.get_value_or_default(".name", "<dep>")
                version = dep.get_value_or_default(".version", "")
                is_pinned = dep.get_value_or_default(".is_pinned", False)

                c.assert_true(
                    is_pinned,
                    f"{path}: chart {name!r} dependency {dep_name!r} version {version!r} is not pinned"
                )

        if not any_dep:
            c.skip("No Helm chart dependencies found to evaluate")

    return c


if __name__ == "__main__":
    main()
