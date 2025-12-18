from lunar_policy import Check, variable_or_default

def check_minreplicas(data=None):
    with Check("k8s-min-replicas", "Valid minReplicas") as c:
        descriptors = c.get_node(".k8s.descriptors")
        if not descriptors.exists():
            return 
        minReplicas = int(variable_or_default("minReplicas", "0"))
        for desc in descriptors:
            if not desc.get_value_or_default(".valid", False):
                continue  # already reported above

            obj = desc.get_node(".contents")
            if not obj.exists():
                continue 
            
            kind = obj.get_value(".kind")
            if kind != "HorizontalPodAutoscaler":
                continue  # ignore non-HPA objects

            spec = obj.get_node(".spec")
            if not spec.exists():
                continue
            
            minr_raw = spec.get_value_or_default(".minReplicas", "0")
            try:
                minr = int(minr_raw)
            except (TypeError, ValueError):
                minr = 0

            meta = obj.get_node(".metadata")
            ns = meta.get_value_or_default(".namespace", "default")
            name = meta.get_value_or_default(".name", "<noname>")
            fname = desc.get_value_or_default(".k8s_file_location", "<file>")

            c.assert_true(
                minr >= minReplicas,
                f"{fname}: HPA {ns}/{name} must have spec.minReplicas >= {minReplicas}, got {minr_raw!r}"
            )
