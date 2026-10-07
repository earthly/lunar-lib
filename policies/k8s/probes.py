from lunar_policy import Check

from helpers import Findings, entries_or_skip


def main(node=None):
    """Requires liveness and readiness probes on all containers."""
    c = Check("probes", "Containers should have liveness and readiness probes", node=node)
    with c:
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")

        findings = Findings(c)
        for workload in workloads:
            kind = workload.get("kind", "")
            # Skip Jobs and CronJobs - probes don't apply
            if kind in ("Job", "CronJob"):
                continue
            name = workload.get("name", "<unknown>")
            namespace = workload.get("namespace", "default")

            for container in workload.get("containers") or []:
                cname = container.get("name", "<container>")
                prefix = f"{kind} {namespace}/{name} container {cname!r}"
                findings.check(container.get("has_liveness_probe") is True, workload, f"{prefix} missing livenessProbe")
                findings.check(container.get("has_readiness_probe") is True, workload, f"{prefix} missing readinessProbe")
        findings.report()

    return c


if __name__ == "__main__":
    main()
