from lunar_policy import Check


def main(node=None):
    """Chart versions must follow semantic versioning."""
    c = Check("version-semver", "Helm chart versions should follow semver", node=node)
    with c:
        charts = c.get_node(".k8s.helm.charts")
        if not charts.exists():
            c.skip("No Helm charts found in this repository")

        for chart in charts:
            path = chart.get_value_or_default(".path", "<unknown>")
            name = chart.get_value_or_default(".name", "<chart>")
            version = chart.get_value_or_default(".version", "")
            is_semver = chart.get_value_or_default(".version_is_semver", False)

            c.assert_true(
                is_semver,
                f"{path}: chart {name!r} version {version!r} is not valid semver (expected X.Y.Z)"
            )

    return c


if __name__ == "__main__":
    main()
