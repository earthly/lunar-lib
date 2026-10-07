from lunar_policy import Check

from helpers import Findings, entries_or_skip, list_input, require_fields


def main(node=None):
    """Fails manifests and rendered charts that use an apiVersion listed in deprecated_api_versions."""
    c = Check("deprecated-api-versions", "Manifests should not use deprecated API versions", node=node)
    with c:
        deprecated = []
        for entry in list_input("deprecated_api_versions"):
            api_version, _, kind = entry.partition(":")
            deprecated.append((api_version, kind))
        if not deprecated:
            c.skip("deprecated_api_versions is not set")
        manifests = entries_or_skip(c, ".k8s.manifests", "No Kubernetes manifests found in this repository")
        require_fields(c, [r for m in manifests for r in m.get("resources") or []], ["api_version"], "apiVersion")

        findings = Findings(c)
        for manifest in manifests:
            for r in manifest.get("resources") or []:
                api_version, kind = r.get("api_version"), r.get("kind")
                what = f"{kind} {r.get('namespace', 'default')}/{r.get('name', '<unknown>')}"
                findings.check(
                    not any(api_version == a and (not k or kind == k) for a, k in deprecated), manifest,
                    f"{what} uses deprecated apiVersion {api_version}"
                )
        findings.report(nothing_checked="No Kubernetes resources found in this repository")

    return c


if __name__ == "__main__":
    main()
