from lunar_policy import Check

from helpers import Findings, describe, entries_or_skip, list_input, require_fields


def main(node=None):
    """Enforces required and forbidden pod template annotations."""
    c = Check("pod-annotations", "Pod templates should carry the required annotations and none of the forbidden ones", node=node)
    with c:
        required = list_input("required_pod_annotations")
        forbidden = list_input("forbidden_pod_annotations")
        if not required and not forbidden:
            c.skip("Neither required_pod_annotations nor forbidden_pod_annotations is set")
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")
        require_fields(c, workloads, ["pod_annotations"], "pod annotations")

        findings = Findings(c)
        for w in workloads:
            annotations = w.get("pod_annotations") or {}
            # A partial manifest (no pod labels, e.g. a kustomize patch) may leave
            # required annotations to the definition it patches.
            for key in required if w.get("pod_labels") else []:
                findings.check(key in annotations, w, f"{describe(w)} pod template is missing required annotation {key}")
            for key in forbidden:
                findings.check(key not in annotations, w, f"{describe(w)} pod template sets forbidden annotation {key}")
        findings.report(nothing_checked="Only partial manifests here, such as kustomize patches, which leave required annotations to the definition they patch")

    return c


if __name__ == "__main__":
    main()
