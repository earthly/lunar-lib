from lunar_policy import Check

from helpers import Findings, describe, entries_or_skip, list_input, require_fields


def normalize(image):
    """registry/path of an image reference, without tag or digest; an image
    with no registry is on docker.io, and an official one under library/."""
    ref = image.split("@", 1)[0]
    if ref.rfind(":") > ref.rfind("/"):
        ref = ref[:ref.rfind(":")]
    parts = ref.split("/")
    if len(parts) == 1 or not ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost"):
        parts = ["docker.io"] + (["library"] if len(parts) == 1 else []) + parts
    if parts[0] in ("index.docker.io", "registry-1.docker.io"):
        parts[0] = "docker.io"
    return "/".join(parts)


def allowed(name, registries):
    return any(name == r or name.startswith(r + "/") for r in registries)


def main(node=None):
    """Requires container and init container images to come from allowed_registries."""
    c = Check("allowed-registries", "Container images should come from an allowed registry", node=node)
    with c:
        registries = [r.rstrip("/") for r in list_input("allowed_registries")]
        if not registries:
            c.skip("allowed_registries is not set")
        workloads = entries_or_skip(c, ".k8s.workloads", "No Kubernetes workloads found in this repository")
        require_fields(c, workloads, ["init_containers"], "init containers")

        findings = Findings(c)
        for w in workloads:
            for ct in (w.get("containers") or []) + (w.get("init_containers") or []):
                image = ct.get("image")
                if not image:
                    continue  # set elsewhere, e.g. by a kustomize images transformer
                name = normalize(image)
                findings.check(
                    allowed(name, registries), w,
                    f"{describe(w)} container {ct.get('name', '<container>')!r} image {image} ({name}) is not from an allowed registry"
                )
        findings.report(nothing_checked="No container images found in this repository")

    return c


if __name__ == "__main__":
    main()
