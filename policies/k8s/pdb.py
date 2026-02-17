from lunar_policy import Check


def main(node=None):
    """Requires PodDisruptionBudgets for Deployments and StatefulSets."""
    c = Check("pdb", "Deployments and StatefulSets should have PodDisruptionBudgets", node=node)
    with c:
        workloads = c.get_node(".k8s.workloads")
        if not workloads.exists():
            c.skip("No Kubernetes workloads found in this repository")

        pdbs = c.get_node(".k8s.pdbs")

        # Build set of (namespace, workload_name) tuples that have PDBs
        pdb_targets = set()
        if pdbs.exists():
            for pdb in pdbs:
                target = pdb.get_value_or_default(".target_workload", "")
                pdb_namespace = pdb.get_value_or_default(".namespace", "default")
                if target:
                    pdb_targets.add((pdb_namespace, target))

        # Check Deployments and StatefulSets have matching PDBs
        for workload in workloads:
            kind = workload.get_value_or_default(".kind", "")

            # Only check Deployments and StatefulSets
            if kind not in ("Deployment", "StatefulSet"):
                continue

            name = workload.get_value_or_default(".name", "<unknown>")
            namespace = workload.get_value_or_default(".namespace", "default")
            path = workload.get_value_or_default(".path", "<unknown>")

            has_pdb = (namespace, name) in pdb_targets
            c.assert_true(
                has_pdb,
                f"{path}: {kind} {namespace}/{name} has no matching PodDisruptionBudget"
            )

    return c


if __name__ == "__main__":
    main()

