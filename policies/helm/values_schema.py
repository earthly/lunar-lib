from lunar_policy import Check


def main(node=None):
    """Charts should ship a values.schema.json to validate user-provided values."""
    c = Check("values-schema", "Helm charts should include values.schema.json", node=node)
    with c:
        charts = c.get_node(".k8s.helm.charts")
        if not charts.exists():
            c.skip("No Helm charts found in this repository")

        for chart in charts:
            path = chart.get_value_or_default(".path", "<unknown>")
            name = chart.get_value_or_default(".name", "<chart>")
            has_schema = chart.get_value_or_default(".has_values_schema", False)

            c.assert_true(
                has_schema,
                f"{path}: chart {name!r} is missing values.schema.json"
            )

    return c


if __name__ == "__main__":
    main()
