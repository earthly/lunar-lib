"""Shared helpers for the container-scan checks."""

import os
import re
from datetime import datetime

from lunar_policy import Node


def _scan_time(scan):
    try:
        stamp = datetime.fromisoformat(scan.get("source", {}).get("collected_at", ""))
        return stamp.timestamp() if stamp.tzinfo is not None else -1
    except (TypeError, ValueError):
        return -1


def scan_for_commit(check):
    """Select complete scan records for the images this commit pushed.

    Merged finding arrays include scheduled scans of older images. Read the
    original records instead: an after-json scan at this SHA establishes each
    pushed image's digest, then only scans of those digests can contribute.
    Later scheduled scans of the same image still count, including new CVEs.
    """
    merged = check.get_node(".container_scan")
    sha = os.environ.get("LUNAR_COMPONENT_GIT_SHA", "")
    # Offline component JSON has no commit context; preserve that interface.
    if not sha:
        return merged, []

    refs = pushed_image_refs(check.get_node(".containers"))
    empty = Node.from_component_json({}, bundle_info={"workflows_finished": True})
    if not refs:
        return empty.get_node(".container_scan"), []
    if not merged.exists():
        return merged, []

    # Bundle/SDK iteration order is not a scan timestamp. A replayed record can
    # arrive later even though its scan is older.
    scans = sorted(check.get_all_values(".container_scan"), key=_scan_time, reverse=True)
    digests = {}
    problems = []
    for scan in scans:
        source = scan.get("source", {})
        if source.get("collected_sha") != sha or source.get("integration") != "after-json":
            continue
        for image in scan.get("images", []):
            ref, digest = image.get("image"), image.get("digest", "")
            if (ref not in refs or not isinstance(digest, str)
                    or not re.fullmatch(r"[a-z0-9]+:[0-9a-f]{32,}", digest)):
                continue
            if ref in digests and digests[ref] != digest:
                problems.append(f"Conflicting scanned digests for {ref} at commit {sha}")
            digests[ref] = digest

    for ref in refs:
        if ref not in digests:
            problems.append(f"No digest-bearing scan of {ref} for commit {sha}")

    severities = ("critical", "high", "medium", "low")
    summary = {f"has_{severity}": False for severity in severities}
    findings = []
    seen = set()
    for scan in scans:
        for image in scan.get("images", []):
            ref = image.get("image")
            if ref not in digests or image.get("digest") != digests[ref]:
                continue
            if _scan_time(scan) < 0:
                problems.append(f"Missing or invalid scan collection time for {ref}")
                continue
            key = (ref, image.get("tool") or scan.get("source", {}).get("tool"))
            if key in seen:
                continue
            seen.add(key)
            counts = image.get("vulnerabilities", {})
            if not all(isinstance(counts.get(s), int) and counts[s] >= 0 for s in severities):
                problems.append(f"Incomplete vulnerability counts for {ref}")
                continue
            for severity in severities:
                summary[f"has_{severity}"] |= bool(
                    image.get("summary", {}).get(f"has_{severity}") or counts[severity] > 0
                )
            for finding in scan.get("findings", []):
                if not finding.get("image"):
                    problems.append(f"Scan findings lack image identity for {ref}")
                elif finding["image"] == ref:
                    findings.append(finding)

    data = {"container_scan": {"summary": summary, "findings": findings}}
    scoped = Node.from_component_json(data, bundle_info={"workflows_finished": True})
    return scoped.get_node(".container_scan"), list(dict.fromkeys(problems))


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
