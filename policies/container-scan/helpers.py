"""Shared helpers for the container-scan checks."""

from datetime import datetime

SEVERITIES = ("critical", "high", "medium", "low")


def _collected_at(scan):
    """`source.collected_at` as an aware datetime, or None if absent or unparseable."""
    value = (scan.get("source") or {}).get("collected_at")
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.utcoffset() is not None else None


def _supersede_key(scan):
    """`(tool, image refs)` of a complete scan, or None if it can't be superseded.

    A scan with errors, partial counts or no image refs is always judged.
    """
    tool = (scan.get("source") or {}).get("tool")
    counts = scan.get("vulnerabilities") or {}
    if not tool or scan.get("errors") or not all(s in counts for s in SEVERITIES):
        return None
    refs = {i["image"] for i in scan.get("images") or [] if isinstance(i, dict) and i.get("image")}
    if not refs and scan.get("image"):
        refs = {scan["image"]}
    return (tool, frozenset(refs)) if refs else None


def scan_snapshots(check):
    """The `.container_scan` payloads to judge, one per scan record.

    The merged `.container_scan` is not one scan: the hub concatenates
    `findings[]` across records but keeps one writer's counts, and on the
    default branch it folds in the latest scheduled rescan even when that
    rescan ran at an older commit, against that commit's images. The records a
    policy bundle carries are only the ones collected at the commit being
    evaluated, so judging records keeps another commit's scan out of the
    verdict. When one scanner recorded several complete scans of the same
    images here, only the newest counts.

    Returns the merged value instead when no record here carries scan results
    (nothing was scanned at this commit), when a record splits counts and
    findings across writes, or when no record has `source.collected_at`
    (collectors older than that field).
    """
    try:
        records = check.get_all_values(".container_scan")
    except ValueError:
        # Collection is over and no record at this commit has scan data. While
        # collection runs, NoDataError propagates and the check stays pending.
        return [check.get_value(".container_scan")]
    scans = [
        r for r in records
        if isinstance(r, dict) and any(k in r for k in ("vulnerabilities", "summary", "findings"))
    ]
    if (
        not scans
        or any("vulnerabilities" not in s and "summary" not in s for s in scans)
        or not any(_collected_at(s) for s in scans)
    ):
        return [check.get_value(".container_scan")]

    dated = [(scan, _supersede_key(scan), _collected_at(scan)) for scan in scans]
    newest = {}
    for _, key, stamp in dated:
        if key is not None and stamp is not None and (key not in newest or stamp > newest[key]):
            newest[key] = stamp
    return [
        scan for scan, key, stamp in dated
        if key is None or stamp is None or stamp >= newest[key]
    ]


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
