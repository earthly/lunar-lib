from lunar_policy import Check, variable_or_default

from helpers import Findings, complete, describe, entries_or_skip, int_input, require_fields


def main(node=None):
    """Requires Deployments and StatefulSets to drain before stopping."""
    c = Check("graceful-shutdown", "Workloads should drain in-flight requests before stopping", node=node)
    with c:
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")
        checked = [w for w in complete(workloads) if w.get("kind") in ("Deployment", "StatefulSet")]
        if not checked:
            c.skip("No Deployments or StatefulSets found in this repository")
        require_fields(c, checked, ["termination_grace_period_seconds"], "shutdown settings")

        min_grace = int_input("min_termination_grace_period_seconds", 30)
        require_prestop = (variable_or_default("require_prestop", "true") or "").strip().lower() != "false"

        findings = Findings(c)
        for w in checked:
            if require_prestop:
                findings.check(any(ct.get("has_prestop") is True for ct in w.get("containers") or []), w,
                               f"{describe(w)} has no container with a preStop hook")
            grace = w.get("termination_grace_period_seconds")
            grace = 30 if grace is None else grace
            findings.check(grace >= min_grace, w,
                           f"{describe(w)} has terminationGracePeriodSeconds {grace}, below {min_grace}")
        findings.report(nothing_checked="No Deployments or StatefulSets found in this repository")

    return c


if __name__ == "__main__":
    main()
