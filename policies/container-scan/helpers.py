"""Shared helpers for the container-scan checks."""


def pushed_ref(cmd):
    """Return the image ref a traced `docker` command shipped, or None.

    Recognises `docker push <ref>` and a build that pushes in one step
    (`docker build --push -t <ref>`, `docker buildx build --push -t <ref>`).
    """
    tokens = cmd.split()
    if not tokens:
        return None
    positional = [t for t in tokens[1:] if not t.startswith("-")]
    if positional and positional[0] == "push":
        after = tokens[tokens.index("push") + 1:]
        refs = [t for t in after if not t.startswith("-")]
        return refs[0] if refs else None
    if "--push" in tokens:
        for i, token in enumerate(tokens[:-1]):
            if token in ("-t", "--tag"):
                return tokens[i + 1]
    return None


def pushed_image_refs(containers_node):
    """Image refs this component pushed, in push order, each counted once.

    Reads the docker collector's native CI record rather than
    `.containers.builds[]`: builds[] is "what was built", so a test build that
    never shipped lands there while a push recorded by a separate CI job does
    not. This is the resolution `container-rescan.sh` uses to choose images, so
    a check gated on it is applicable exactly when the scanner had a target.
    """
    cmds = containers_node.get_node(".native.docker.cicd.cmds")
    if not cmds.exists():
        return []
    refs = []
    for entry in cmds:
        ref = pushed_ref(entry.get_value_or_default(".cmd", "") or "")
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def no_scan_data_reasons(refs):
    """Failure lines for a commit with no `.container_scan`, one per line.

    The single line this replaced ("Ensure a scanner (Trivy, Grype, etc.) is
    configured") reads as a configuration gap, and that is usually not what
    happened: a scanner is configured, it ran, and it recorded nothing for this
    commit. State what the Component JSON can actually answer — how many images
    this commit pushed and which ones have no results — and leave both readings
    open.
    """
    pushed = f", though it pushed {len(refs)} image(s)" if refs else ""
    head = (
        f"No container scan results at this commit{pushed} — either no scanner is "
        "configured for this component, or a configured one recorded nothing here."
    )
    return [head] + [f"not scanned: {ref}" for ref in refs]
