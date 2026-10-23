from lunar_policy import Check

from helpers import Findings, entries_or_skip


def main(node=None):
    """Fails when workload PodSpecs set hostIPC: true."""
    c = Check("host-ipc", "Workload PodSpecs should not set hostIPC: true", node=node)
    with c:
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")

        findings = Findings(c)
        for workload in workloads:
            kind = workload.get("kind", "")
            name = workload.get("name", "<unknown>")
            namespace = workload.get("namespace", "default")
            findings.check(
                workload.get("host_ipc", False) is not True, workload,
                f"{kind} {namespace}/{name} should not set spec.hostIPC: true (workload shares the host IPC namespace)"
            )
        findings.report()

    return c


if __name__ == "__main__":
    main()
