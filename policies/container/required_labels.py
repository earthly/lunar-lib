"""Check that containers have required labels (from Dockerfile and/or build commands)."""

from lunar_policy import Check, variable_or_default


def main():
    with Check("required-labels", "Containers should have required labels") as c:
        required_str = variable_or_default("required_labels", "")
        required = [l.strip() for l in required_str.split(",") if l.strip()]

        if not required:
            return

        # Collect all labels from Dockerfile definitions
        dockerfile_labels = {}
        definitions = c.get_node(".containers.definitions")
        if definitions.exists():
            for definition in definitions:
                if not definition.get_value_or_default(".valid", False):
                    continue
                labels = definition.get_value_or_default(".labels", {})
                dockerfile_labels.update(labels)

        # Collect all labels from build commands
        build_labels = {}
        builds = c.get_node(".containers.builds")
        if builds.exists():
            for build in builds:
                labels = build.get_value_or_default(".labels", {})
                build_labels.update(labels)

        # Union of both sources
        all_labels = {**dockerfile_labels, **build_labels}

        missing = [l for l in required if l not in all_labels]

        if missing:
            c.fail(f"Missing required labels: {', '.join(missing)}")


if __name__ == "__main__":
    main()
