from lunar_policy import Check, variable_or_default


def main(node=None):
    """Enforces minimum replica counts on HPAs."""
    c = Check("min-replicas", "HPAs should have minimum replica counts", node=node)
    with c:
        hpas = c.get_node(".k8s.hpas")
        if not hpas.exists():
            c.skip("No HorizontalPodAutoscalers found in this repository")
            return c

        try:
            min_required = int(variable_or_default("min_replicas", "3"))
        except ValueError:
            min_required = 3

        for hpa in hpas:
            name = hpa.get_value_or_default(".name", "<unknown>")
            namespace = hpa.get_value_or_default(".namespace", "default")
            path = hpa.get_value_or_default(".path", "<unknown>")
            min_replicas = hpa.get_value_or_default(".min_replicas", 0)

            c.assert_true(
                min_replicas >= min_required,
                f"{path}: HPA {namespace}/{name} has minReplicas={min_replicas}, need at least {min_required}"
            )

    return c


if __name__ == "__main__":
    main()

