from lunar_policy import Check

from helpers import Findings, autoscalers_of, complete, describe, entries, entries_or_skip, require_fields


def main(node=None):
    """Forbids spec.replicas on a workload an HPA or KEDA ScaledObject scales."""
    c = Check("no-static-replicas", "Autoscaled workloads should leave spec.replicas unset", node=node)
    with c:
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")
        hpas, scaled_objects = entries(c, ".k8s.hpas"), entries(c, ".k8s.scaled_objects")
        if not hpas and not scaled_objects:
            c.skip("No HorizontalPodAutoscalers or ScaledObjects found in this repository")
        checked = [w for w in complete(workloads) if w.get("kind") in ("Deployment", "StatefulSet")]
        require_fields(c, checked, ["replicas_set"], "replicas_set")

        findings = Findings(c)
        for w in checked:
            for kind, autoscaler in autoscalers_of(w, hpas, scaled_objects):
                findings.check(w.get("replicas_set") is not True, w,
                               f"{describe(w)} sets spec.replicas: {w.get('replicas')} while {kind} {autoscaler.get('name')} scales it")
        findings.report(nothing_checked="No HorizontalPodAutoscaler or ScaledObject scales a Deployment or StatefulSet in this repository")

    return c


if __name__ == "__main__":
    main()
