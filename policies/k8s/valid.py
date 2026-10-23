from lunar_policy import Check

from helpers import Findings, entries_or_skip


def main(node=None):
    """Validates that all K8s manifests are syntactically correct, and that Helm charts render."""
    c = Check("valid", "All K8s manifests should be valid", node=node)
    with c:
        manifests = entries_or_skip(c, ".k8s.manifests", "No Kubernetes manifests found in this repository")

        findings = Findings(c)
        for manifest in manifests:
            error = manifest.get("error") or "Unknown validation error"
            findings.check(manifest.get("valid") is True, manifest, error)
        findings.report()

    return c


if __name__ == "__main__":
    main()
