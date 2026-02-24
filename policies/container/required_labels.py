"""Check that containers have required labels (from Dockerfile and/or build commands)."""

from lunar_policy import Check, variable_or_default


def _normalize_path(path):
    """Strip leading ./ for consistent matching."""
    if path and path.startswith("./"):
        return path[2:]
    return path


def main():
    with Check("required-labels", "Containers should have required labels") as c:
        required_str = variable_or_default("required_labels", "")
        required = [l.strip() for l in required_str.split(",") if l.strip()]

        if not required:
            return

        definitions = c.get_node(".containers.definitions")
        builds = c.get_node(".containers.builds")

        if not definitions.exists() and not builds.exists():
            return

        # Index build labels by dockerfile path
        build_labels_by_dockerfile = {}
        if builds.exists():
            for build in builds:
                df = _normalize_path(
                    build.get_value_or_default(".dockerfile", "Dockerfile")
                ) or "Dockerfile"
                labels = build.get_value_or_default(".labels", {})
                if df not in build_labels_by_dockerfile:
                    build_labels_by_dockerfile[df] = {}
                build_labels_by_dockerfile[df].update(labels)

        checked_dockerfiles = set()

        # Check each Dockerfile definition with its matching build labels
        if definitions.exists():
            for definition in definitions:
                if not definition.get_value_or_default(".valid", False):
                    continue

                path = _normalize_path(definition.get_value(".path"))
                checked_dockerfiles.add(path)

                # Labels from this Dockerfile's LABEL instructions
                def_labels = definition.get_value_or_default(".labels", {})

                # Labels from matching build commands
                matching_build_labels = build_labels_by_dockerfile.get(path, {})

                # Union of both sources for this Dockerfile
                all_labels = {**def_labels, **matching_build_labels}

                missing = [l for l in required if l not in all_labels]
                if missing:
                    c.fail(
                        f"'{path}' missing required labels: {', '.join(missing)}"
                    )

        # Check builds that don't match any Dockerfile definition
        for df_path, labels in build_labels_by_dockerfile.items():
            if df_path not in checked_dockerfiles:
                missing = [l for l in required if l not in labels]
                if missing:
                    c.fail(
                        f"Build for '{df_path}' missing required labels: "
                        f"{', '.join(missing)}"
                    )


if __name__ == "__main__":
    main()
