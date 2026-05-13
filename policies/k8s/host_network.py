from lunar_policy import Check


def main(node=None):
    """Fails when workload PodSpecs set hostNetwork: true."""
    c = Check("host-network", "Workload PodSpecs should not set hostNetwork: true", node=node)
    with c:
        workloads = c.get_node(".k8s.workloads")
        if not workloads.exists():
            c.skip("No Kubernetes workloads found in this repository")

        for workload in workloads:
            kind = workload.get_value_or_default(".kind", "")
            name = workload.get_value_or_default(".name", "<unknown>")
            namespace = workload.get_value_or_default(".namespace", "default")
            path = workload.get_value_or_default(".path", "<unknown>")

            host_network = workload.get_value_or_default(".host_network", False)

            c.assert_true(
                host_network is not True,
                f"{path}: {kind} {namespace}/{name} should not set spec.hostNetwork: true (workload shares the host network namespace)"
            )

    return c


if __name__ == "__main__":
    main()
