"""Check that container builds include required labels."""

from lunar_policy import Check, variable_or_default


def main():
    with Check("build-required-labels", "Container builds should include required labels") as c:
        required_str = variable_or_default("required_build_labels", "")
        required = [l.strip() for l in required_str.split(",") if l.strip()]

        if not required:
            return

        builds = c.get_node(".containers.builds")
        if not builds.exists():
            return

        for build in builds:
            cmd = build.get_value_or_default(".cmd", "<unknown>")
            labels = build.get_value_or_default(".labels", {})

            missing = [l for l in required if l not in labels]

            if missing:
                c.fail(f"Build '{cmd}' is missing required labels: {', '.join(missing)}")


if __name__ == "__main__":
    main()
