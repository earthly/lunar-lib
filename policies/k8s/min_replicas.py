from lunar_policy import Check, variable_or_default

from helpers import Findings, entries_or_skip


def main(node=None):
    """Enforces minimum replica counts on HPAs."""
    c = Check("min-replicas", "HPAs should have minimum replica counts", node=node)
    with c:
        hpas = entries_or_skip(c, ".k8s.hpas", "No HorizontalPodAutoscalers found in this repository")

        try:
            min_required = int(variable_or_default("min_replicas", "3"))
        except ValueError:
            min_required = 3

        findings = Findings(c)
        for hpa in hpas:
            name = hpa.get("name", "<unknown>")
            namespace = hpa.get("namespace", "default")
            min_replicas = hpa.get("min_replicas") or 0
            findings.check(
                min_replicas >= min_required, hpa,
                f"HPA {namespace}/{name} has minReplicas={min_replicas}, need at least {min_required}"
            )
        findings.report()

    return c


if __name__ == "__main__":
    main()
