from lunar_policy import Check


def selector_matches(selector, labels):
    """Kubernetes LabelSelector semantics, as a policy/v1 PodDisruptionBudget
    applies them: matchLabels is an AND of equalities, matchExpressions supports
    In / NotIn / Exists / DoesNotExist, an empty selector matches every pod in
    the namespace, and a null selector matches none."""
    if not isinstance(selector, dict):
        return False
    labels = {str(k): str(v) for k, v in (labels or {}).items()}
    for key, value in (selector.get("matchLabels") or {}).items():
        if labels.get(str(key)) != str(value):
            return False
    for expr in selector.get("matchExpressions") or []:
        key = str(expr.get("key", ""))
        values = {str(v) for v in (expr.get("values") or [])}
        operator = expr.get("operator")
        if operator == "In":
            ok = key in labels and labels[key] in values
        elif operator == "NotIn":
            ok = key not in labels or labels[key] not in values
        elif operator == "Exists":
            ok = key in labels
        elif operator == "DoesNotExist":
            ok = key not in labels
        else:
            ok = False  # the API server rejects any other operator
        if not ok:
            return False
    return True


def main(node=None):
    """Requires PodDisruptionBudgets for Deployments and StatefulSets."""
    c = Check("pdb", "Deployments and StatefulSets should have PodDisruptionBudgets", node=node)
    with c:
        workloads = c.get_node(".k8s.workloads")
        if not workloads.exists():
            c.skip("No Kubernetes workloads found in this repository")

        pdbs = []
        pdbs_node = c.get_node(".k8s.pdbs")
        if pdbs_node.exists():
            pdbs = [pdb.get_value() for pdb in pdbs_node]

        for workload_node in workloads:
            workload = workload_node.get_value()
            kind = workload.get("kind", "")

            # Only check Deployments and StatefulSets
            if kind not in ("Deployment", "StatefulSet"):
                continue

            name = workload.get("name", "<unknown>")
            namespace = workload.get("namespace", "default")
            path = workload.get("path", "<unknown>")
            same_ns = [p for p in pdbs if p.get("namespace", "default") == namespace]

            if "pod_labels" in workload:
                has_pdb = any(selector_matches(p.get("selector"), workload["pod_labels"]) for p in same_ns)
            else:
                # Collected by a k8s collector that predates pod_labels/selector:
                # fall back to its guessed target name.
                has_pdb = any(p.get("target_workload") == name for p in same_ns)

            c.assert_true(
                has_pdb,
                f"{path}: {kind} {namespace}/{name} has no matching PodDisruptionBudget"
            )

    return c


if __name__ == "__main__":
    main()
