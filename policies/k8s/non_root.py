from lunar_policy import Check


def main(node=None):
    """Requires containers to run as non-root users."""
    c = Check("non-root", "Containers should run as non-root", node=node)
    with c:
        workloads = c.get_node(".k8s.workloads")
        if not workloads.exists():
            c.skip("No Kubernetes workloads found in this repository")
            return c

        for workload in workloads:
            kind = workload.get_value_or_default(".kind", "")
            name = workload.get_value_or_default(".name", "<unknown>")
            namespace = workload.get_value_or_default(".namespace", "default")
            path = workload.get_value_or_default(".path", "<unknown>")

            containers = workload.get_node(".containers")
            if not containers.exists():
                continue

            for container in containers:
                cname = container.get_value_or_default(".name", "<container>")
                runs_as_non_root = container.get_value_or_default(".runs_as_non_root", False)

                c.assert_true(
                    runs_as_non_root,
                    f"{path}: {kind} {namespace}/{name} container {cname!r} should set securityContext.runAsNonRoot: true"
                )

    return c


if __name__ == "__main__":
    main()

