from lunar_policy import Check

from helpers import Findings, entries_or_skip


def main(node=None):
    """Requires workload PodSpecs to set hostUsers: false (K8s User Namespaces)."""
    c = Check("host-users", "Workload PodSpecs should set hostUsers: false", node=node)
    with c:
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")

        findings = Findings(c)
        for workload in workloads:
            kind = workload.get("kind", "")
            name = workload.get("name", "<unknown>")
            namespace = workload.get("namespace", "default")
            findings.check(
                workload.get("host_users", True) is False, workload,
                f"{kind} {namespace}/{name} should set spec.hostUsers: false (Kubernetes user namespaces, GA in v1.36)"
            )
        findings.report()

    return c


if __name__ == "__main__":
    main()
