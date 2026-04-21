from lunar_policy import Check


def main(node=None):
    """All Helm charts must pass `helm lint`."""
    c = Check("lint-passed", "Helm charts should pass helm lint", node=node)
    with c:
        charts = c.get_node(".k8s.helm.charts")
        if not charts.exists():
            c.skip("No Helm charts found in this repository")

        for chart in charts:
            path = chart.get_value_or_default(".path", "<unknown>")
            name = chart.get_value_or_default(".name", "<chart>")
            lint_passed = chart.get_value_or_default(".lint_passed", False)

            errors = chart.get_node(".lint_errors")
            error_msg = ""
            if errors.exists():
                error_msg = "; ".join(str(e.get_value()) for e in errors)

            suffix = f": {error_msg}" if error_msg else ""
            c.assert_true(
                lint_passed,
                f"{path}: chart {name!r} failed helm lint{suffix}"
            )

    return c


if __name__ == "__main__":
    main()
