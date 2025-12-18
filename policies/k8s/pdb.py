from lunar_policy import Check

WORKLOAD_KINDS = ["Deployment", "StatefulSet"]

def check_pdb(data=None):
    with Check("k8s-pdb-per-workload", "PDB per workload") as c:
        descriptors = c.get_node(".k8s.descriptors")
        if not descriptors.exists():
            return 
        pdbs = []
        workloads = []
        # collect PDBs and workloads
        for desc in descriptors:
            if not desc.get_value_or_default(".valid", False):
                continue
            obj = desc.get_node(".contents")
            if not obj.exists():
                continue

            kind = obj.get_value(".kind")
            ns, name = _ns_name(obj)

            if kind == "PodDisruptionBudget":
                spec = obj.get_node(".spec")
                if not spec.exists():
                    continue
                selector = spec.get_value(".selector")
                has_budget = spec.exists(".minAvailable") or spec.exists(".maxUnavailable")
                pdbs.append({"ns": ns, "name": name, "selector": selector, "has_budget": has_budget})
            elif kind in WORKLOAD_KINDS:
                workloads.append({
                    "ns": ns,
                    "name": name,
                    "labels": _pod_labels(obj),
                    "file": desc.get_value_or_default(".k8s_file_location", "<file>"),
                })

        # assert each workload has a matching PDB with a valid selector + budget field
        for w in workloads:
            match = next(
                (p for p in pdbs
                if p["ns"] == w["ns"]
                and p["has_budget"]
                and _selector_matches(p["selector"], w["labels"])),
                None
            )
            c.assert_true(
                match is not None,
                f"{w['file']}: {w['ns']}/{w['name']} has no matching PodDisruptionBudget "
            )
        

def _ns_name(obj):
    meta = obj.get_node(".metadata")
    ns = meta.get_value_or_default(".namespace", "default")
    name = meta.get_value_or_default(".name", "<noname>")
    return (ns, name)

def _pod_labels(obj):
    return obj.get_value_or_default(".spec.template.metadata.labels", {})

def _selector_matches(selector, labels):
    if not selector or not isinstance(labels, dict):
        return False
    # matchLabels
    for k, v in (selector.get("matchLabels") or {}).items():
        if labels.get(k) != v:
            return False
    # matchExpressions
    for expr in (selector.get("matchExpressions") or []):
        key = expr.get("key")
        op = expr.get("operator")
        vals = expr.get("values") or []
        if op == "In" and labels.get(key) not in vals:
            return False
        if op == "NotIn" and labels.get(key) in vals:
            return False
        if op == "Exists" and key not in labels:
            return False
        if op == "DoesNotExist" and key in labels:
            return False
        if op not in {"In", "NotIn", "Exists", "DoesNotExist"}:
            return False
    return True
