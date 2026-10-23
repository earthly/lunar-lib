from lunar_policy import Check

from helpers import Findings, entries_or_skip


def main(node=None):
    """Requires containers to run as non-root users."""
    c = Check("non-root", "Containers should run as non-root", node=node)
    with c:
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")

        findings = Findings(c)
        for workload in workloads:
            kind = workload.get("kind", "")
            name = workload.get("name", "<unknown>")
            namespace = workload.get("namespace", "default")

            for container in workload.get("containers") or []:
                cname = container.get("name", "<container>")
                findings.check(
                    container.get("runs_as_non_root") is True, workload,
                    f"{kind} {namespace}/{name} container {cname!r} should set securityContext.runAsNonRoot: true"
                )
        findings.report()

    return c


if __name__ == "__main__":
    main()
