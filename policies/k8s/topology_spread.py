from lunar_policy import Check, variable_or_default

from helpers import (Findings, autoscalers_of, complete, describe, entries, entries_or_skip, int_input,
                     replica_range, require_fields, selector_matches)


def problems(constraint, labels, max_skew, when, require_match_label_keys):
    found = []
    if not selector_matches(constraint.get("label_selector"), labels):
        found.append("its labelSelector doesn't select the workload's pods")
    if (constraint.get("max_skew") or 0) > max_skew:
        found.append(f"maxSkew {constraint.get('max_skew')} is above {max_skew}")
    if when and constraint.get("when_unsatisfiable") != when:
        found.append(f"whenUnsatisfiable is {constraint.get('when_unsatisfiable')}, not {when}")
    if require_match_label_keys and "pod-template-hash" not in (constraint.get("match_label_keys") or []):
        found.append("matchLabelKeys doesn't include pod-template-hash")
    return found


def main(node=None):
    """Requires a topology spread constraint on workloads that can run more than one replica."""
    c = Check("topology-spread", "Workloads that run several replicas should spread them across zones", node=node)
    with c:
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")
        checked = [w for w in complete(workloads) if w.get("kind") in ("Deployment", "StatefulSet")]
        if not checked:
            c.skip("No Deployments or StatefulSets found in this repository")
        require_fields(c, checked, ["topology_spread_constraints"], "topology spread constraints")

        key = variable_or_default("topology_key", "topology.kubernetes.io/zone") or "topology.kubernetes.io/zone"
        max_skew = int_input("topology_max_skew", 1)
        when = (variable_or_default("topology_when_unsatisfiable", "") or "").strip()
        require_mlk = (variable_or_default("topology_require_match_label_keys", "false") or "").strip().lower() == "true"
        hpas, scaled_objects = entries(c, ".k8s.hpas"), entries(c, ".k8s.scaled_objects")

        findings = Findings(c)
        for w in checked:
            _, largest = replica_range(w, autoscalers_of(w, hpas, scaled_objects))
            if largest <= 1:
                continue
            on_key = [t for t in w.get("topology_spread_constraints") or [] if t.get("topology_key") == key]
            if not on_key:
                findings.fail(w, f"{describe(w)} has no topologySpreadConstraint on {key}")
                continue
            issues = [problems(t, w.get("pod_labels"), max_skew, when, require_mlk) for t in on_key]
            if all(issues):
                findings.fail(w, f"{describe(w)} topologySpreadConstraint on {key}: {'; '.join(min(issues, key=len))}")
            else:
                findings.check(True, w, f"{describe(w)} spreads on {key}")
        findings.report(nothing_checked="No Deployment or StatefulSet in this repository can run more than one replica")

    return c


if __name__ == "__main__":
    main()
