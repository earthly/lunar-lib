from lunar_policy import Check


def main(node=None):
    """Requires liveness and readiness probes on all containers."""
    c = Check("probes", "Containers should have liveness and readiness probes", node=node)
    with c:
        workloads = c.get_node(".k8s.workloads")
        if not workloads.exists():
            c.skip("No Kubernetes workloads found in this repository")

        for workload in workloads:
            kind = workload.get_value_or_default(".kind", "")
            name = workload.get_value_or_default(".name", "<unknown>")
            namespace = workload.get_value_or_default(".namespace", "default")
            path = workload.get_value_or_default(".path", "<unknown>")

            # Skip Jobs and CronJobs - probes don't apply
            if kind in ("Job", "CronJob"):
                continue

            containers = workload.get_node(".containers")
            if not containers.exists():
                continue

            for container in containers:
                cname = container.get_value_or_default(".name", "<container>")
                prefix = f"{path}: {kind} {namespace}/{name} container {cname!r}"

                has_liveness = container.get_value_or_default(".has_liveness_probe", False)
                has_readiness = container.get_value_or_default(".has_readiness_probe", False)

                c.assert_true(has_liveness, f"{prefix} missing livenessProbe")
                c.assert_true(has_readiness, f"{prefix} missing readinessProbe")

    return c


if __name__ == "__main__":
    main()

