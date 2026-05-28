from lunar_policy import Check


def main(node=None):
    """Requires workload PodSpecs to set hostUsers: false (K8s User Namespaces)."""
    c = Check("host-users", "Workload PodSpecs should set hostUsers: false", node=node)
    with c:
        workloads = c.get_node(".k8s.workloads")
        if not workloads.exists():
            c.skip("No Kubernetes workloads found in this repository")

        for workload in workloads:
            kind = workload.get_value_or_default(".kind", "")
            name = workload.get_value_or_default(".name", "<unknown>")
            namespace = workload.get_value_or_default(".namespace", "default")
            path = workload.get_value_or_default(".path", "<unknown>")

            host_users = workload.get_value_or_default(".host_users", True)

            c.assert_true(
                host_users is False,
                f"{path}: {kind} {namespace}/{name} should set spec.hostUsers: false (Kubernetes user namespaces, GA in v1.36)"
            )

    return c


if __name__ == "__main__":
    main()
