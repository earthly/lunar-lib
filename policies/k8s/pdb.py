from lunar_policy import Check

from helpers import Findings, entries_or_skip, identity, same_release, selector_matches


def main(node=None):
    """Requires PodDisruptionBudgets for Deployments and StatefulSets."""
    c = Check("pdb", "Deployments and StatefulSets should have PodDisruptionBudgets", node=node)
    with c:
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")

        pdbs = []
        pdbs_node = c.get_node(".k8s.pdbs")
        if pdbs_node.exists():
            pdbs = [pdb.get_value() for pdb in pdbs_node]

        def selected(workload):
            ns = workload.get("namespace", "default")
            return any(selector_matches(p.get("selector"), workload["pod_labels"])
                       for p in pdbs if p.get("namespace", "default") == ns and same_release(workload, p))

        # Only check Deployments and StatefulSets
        checked = [w for w in workloads if w.get("kind") in ("Deployment", "StatefulSet")]

        # apps/v1 requires pod template labels, so an entry without any is a partial
        # manifest (e.g. a kustomize patch): it takes the verdict of the complete
        # definition it patches.
        complete = {}
        for workload in checked:
            if workload.get("pod_labels"):
                complete[identity(workload)] = complete.get(identity(workload), False) or selected(workload)

        findings = Findings(c)
        for workload in checked:
            kind = workload.get("kind")
            name = workload.get("name", "<unknown>")
            namespace = workload.get("namespace", "default")

            if workload.get("pod_labels"):
                has_pdb = selected(workload)
            elif identity(workload) in complete:
                has_pdb = complete[identity(workload)]
            else:
                # No labels anywhere (a patch of a remote base, or a collector that
                # predates pod_labels): fall back to the collector's name guess.
                has_pdb = any(p.get("target_workload") == name for p in pdbs
                              if p.get("namespace", "default") == namespace)

            findings.check(has_pdb, workload, f"{kind} {namespace}/{name} has no matching PodDisruptionBudget")
        findings.report()

    return c


if __name__ == "__main__":
    main()
