"""Ensure no findings at or above the configured severity threshold.

When findings cross the threshold the check fails with one assertion per
offending package/CVE (when the collector emitted per-finding detail in
`.container_scan.findings[]`), so the hub renders and truncates the list. This
mirrors the `sca` policy's `max-severity` output so a container-image scan and
a code-level SCA scan read identically in the GitHub check / PR comment. When
the scan covered several images, each line names the image(s) the finding was
seen in.

Set `ignore_unfixable: "true"` to narrow the failure to findings that carry an
upgrade target, so an unfixable base-image CVE cannot hold a gate closed
indefinitely. The default (`"false"`) fails on every finding at or above the
threshold, fixable or not. Unfixable findings are always still recorded in the
component JSON — the option changes the *verdict*, never what is collected.

`exempt_findings` lists vulnerabilities that were reviewed and accepted, by id
and exact package version, optionally limited to some images (see
exemptions.py). Exempt findings drop out of the verdict the same way, and so do
findings with no fix covered by an exemption record (see exemption_records.py).
"""

import re
import sys
from datetime import datetime

from exemption_records import ExemptionRecord, find_record, load_records
from exemptions import find_exemption, format_exemptions, parse_exempt_findings
from helpers import no_scan_data_reasons, pushed_image_refs
from lunar_policy import Check, Node, NoDataError, variable_or_default

SEVERITY_ORDER = ["critical", "high", "medium", "low"]


def _snapshot_key(scan):
    source = scan.get("source") or {}
    tool = source.get("tool")
    counts = scan.get("vulnerabilities") or {}
    if (
        not tool or scan.get("errors")
        or not all(severity in counts for severity in SEVERITY_ORDER)
    ):
        return None
    images = scan.get("images") or []
    refs = {image["image"] for image in images if image.get("image")}
    if not refs and scan.get("image"):
        refs = {scan["image"]}
    return (tool, frozenset(refs)) if refs else None


def _inventory_scope(scan):
    source = scan.get("source") or {}
    images = scan.get("images") or []
    counts = scan.get("vulnerabilities") or {}
    summary = scan.get("summary") or {}
    if (
        source.get("integration") not in ("after-json", "cron")
        or not images or scan.get("errors")
        or not all(image.get("image") for image in images)
        or not all(severity in counts for severity in SEVERITY_ORDER)
        or not all(f"has_{severity}" in summary for severity in ("critical", "high"))
    ):
        return None
    sha = source.get("collected_sha") or ""
    scope = set()
    for image in images:
        ref = image["image"]
        tag = ref.rsplit("/", 1)[-1].rpartition(":")[2]
        # Only commit-derived tags identify an inventory across releases.
        # Static tags (e.g. staging/production) are independent scan targets.
        if "@" not in ref and re.fullmatch(r"[0-9a-f]{7,40}", tag) and sha.startswith(tag):
            scope.add((ref.rsplit(":", 1)[0], "commit"))
        else:
            scope.add((ref, "ref"))
    return frozenset(scope)


def _collected_at(scan):
    value = (scan.get("source") or {}).get("collected_at")
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return timestamp if timestamp.utcoffset() is not None else None


def _scan_snapshots(c):
    """Keep coherent scan payloads; merged arrays retain superseded cron CVEs."""
    try:
        snapshots = c.get_all_values(".container_scan")
    except (ValueError, NoDataError):
        return [c.get_value(".container_scan")]
    snapshots = [
        scan for scan in snapshots
        if isinstance(scan, dict) and any(
            key in scan for key in ("vulnerabilities", "summary", "findings")
        )
    ]
    if not snapshots:
        return [c.get_value(".container_scan")]

    # Older collectors may write counts and findings in separate deltas. Their
    # records do not contain complete snapshots, so retain the merged behavior.
    if any(not any(k in scan for k in ("vulnerabilities", "summary")) for scan in snapshots):
        return [c.get_value(".container_scan")]

    dated = [(scan, _snapshot_key(scan), _collected_at(scan)) for scan in snapshots]
    if not any(key is not None and timestamp is not None for _, key, timestamp in dated):
        return [c.get_value(".container_scan")]

    latest = {}
    inventories = {}
    pushed = set(pushed_image_refs(c.get_node(".containers")))
    for scan, key, timestamp in dated:
        if key is None or timestamp is None:
            continue
        latest[key] = max(timestamp, latest.get(key, timestamp))
        scope = _inventory_scope(scan)
        # Replacing SHA tags requires a complete scan of this commit's pushed
        # refs. Separate configured image inventories must remain independent.
        if scope and pushed and pushed == key[1]:
            inventory_key = key[0], scope
            inventories[inventory_key] = max(timestamp, inventories.get(inventory_key, timestamp))

    selected = []
    for scan, key, timestamp in dated:
        if key is not None and timestamp is not None:
            newest = latest[key]
            scope = _inventory_scope(scan)
            if scope:
                newest = max(newest, inventories.get((key[0], scope), timestamp))
            if timestamp < newest:
                continue
        selected.append(scan)
    return selected


def _severities_in_scope(min_severity):
    return SEVERITY_ORDER[: SEVERITY_ORDER.index(min_severity) + 1]


def finding_text(finding):
    """Render one normalized finding as a human-readable line.

    Matches the `sca` policy's format so container and code findings read
    identically: `<severity>: <package> — <cve> (fix: <version>)`.
    """
    severity = finding.get("severity") or "unknown"
    package = finding.get("package")
    cve = finding.get("id")
    head = f"{severity}: {package}" if package else severity
    if cve:
        head += f" — {cve}"
    fix = finding.get("fix_version")
    text = head + (f" (fix: {fix})" if fix else " (no fix available)")
    images = finding.get("images") or []
    if images:
        # Multi-image scans tag each finding with the image it was found in; a
        # vulnerability shared by several images renders once, naming them all.
        text += " [" + ", ".join(images) + "]"
    return text


def _dedupe_findings(findings):
    """Collapse the same vulnerability reported by more than one scanner.

    trivy and grype both write `.container_scan` for the same image, and the hub
    concatenates their `findings[]` while keeping a single writer's counts — so
    one vulnerability appears once per scanner. Enumerating those raw repeats
    identical lines in the PR comment and inflates the "+N more" tail.

    The CVE id *is* the identity, so a finding without one is never merged: a
    scanner may report an advisory it has no CVE for, and collapsing those on
    package and severity alone would discard genuinely distinct vulnerabilities.

    On a collision the *fixable* entry wins, along with its `fix_version`: if any
    scanner knows of a fix then a fix genuinely exists, and preferring it keeps
    the `ignore_unfixable` filter on the safe side — it can only leave a finding
    in scope, never drop one. First-seen order is preserved.
    """
    out = []
    at = {}
    for finding in findings:
        if not finding["id"]:
            out.append(finding)
            continue
        key = (finding["severity"], finding["package"], finding["id"])
        if key not in at:
            at[key] = len(out)
            out.append(finding)
            continue
        kept = out[at[key]]
        # The same vulnerability in several images (or from both scanners) is one
        # line; keep every image it was seen in, in first-seen order.
        images = list(kept["images"])
        images += [i for i in finding["images"] if i not in images]
        if finding["fixable"] and not kept["fixable"]:
            kept = dict(finding)
        kept["images"] = images
        out[at[key]] = kept
    return out


def _collect_findings(scan_node, in_scope, exemptions=(), records=()):
    """Return `(findings, exempted)` at/above threshold from
    `.container_scan.findings[]`.

    Both are empty when the collector did not emit per-finding detail (e.g. a
    summary-only scan) — the failure message then stays the headline alone,
    same as the `sca` policy. Exemptions are matched per image, before the
    dedupe merges images, so a vulnerability exempted in one image still fails
    in another. Each exempted finding carries the `exemption` it matched: an
    `exempt_findings` entry, or an exemption record when it has no fix.
    """
    findings_node = scan_node.get_node(".findings")
    if not findings_node.exists():
        return [], []
    out = []
    exempted = []
    for finding in findings_node:
        severity = (finding.get_value_or_default(".severity", "") or "").lower()
        if severity not in in_scope:
            continue
        fix_version = finding.get_value_or_default(".fix_version", None)
        fixable = finding.get_value_or_default(".fixable", None)
        if fixable is None:
            # Older blobs may omit the flag; a reported fix version is the best
            # available proxy. It is exactly how trivy computes it, and grype
            # only carries a fix version for findings it marks fixed.
            fixable = bool(fix_version)
        entry = {
            "id": finding.get_value_or_default(".cve", None),
            "severity": severity,
            "package": finding.get_value_or_default(".package", None),
            "version": finding.get_value_or_default(".version", None),
            "fix_version": fix_version,
            "fixable": bool(fixable),
            # Set by multi-image scans; absent on single-image blobs.
            "images": [i for i in [finding.get_value_or_default(".image", None)] if i],
        }
        exemption = find_exemption(
            exemptions,
            entry["id"],
            entry["package"],
            entry["version"],
            entry["images"][0] if entry["images"] else None,
        ) or find_record(records, entry["id"], entry["fixable"])
        if exemption:
            exempted.append(dict(entry, exemption=exemption))
        else:
            out.append(entry)
    return _dedupe_findings(out), _dedupe_findings(exempted)


def _exempted_by(exempted):
    """Name where the matched exemptions came from."""
    sources = {
        "exemption records" if isinstance(f["exemption"], ExemptionRecord) else "exempt_findings"
        for f in exempted
    }
    return " and ".join(sorted(sources))


def _exempted_suffix(exempted):
    return (
        f" — {len(exempted)} exempted by {_exempted_by(exempted)}: "
        f"{format_exemptions([f['exemption'] for f in exempted])}"
    )


def _most_severe(findings):
    """Return the most severe severity present in `findings` (None when empty)."""
    for severity in SEVERITY_ORDER:
        if any(f.get("severity") == severity for f in findings):
            return severity
    return None


def _rank(finding):
    """Sort key: most-severe first, then package, then CVE id (stable order)."""
    severity = finding.get("severity")
    return (
        SEVERITY_ORDER.index(severity) if severity in SEVERITY_ORDER else len(SEVERITY_ORDER),
        finding.get("package") or "",
        finding.get("id") or "",
    )


def _evaluate_scan(c, scan_node, in_scope, min_severity, ignore_unfixable, exemptions):
    """Evaluate a snapshot without borrowing another scan's counts or findings."""
    # Determine the failing severity: summary booleans first (preferred),
    # then counts. Build the same human-readable headline we fail with.
    fail_message = None
    for severity in in_scope:
        summary = scan_node.get_node(f".summary.has_{severity}")
        if summary.exists() and summary.get_value():
            fail_message = f"{severity.capitalize()} container vulnerabilities detected"
            break
    if fail_message is None:
        for severity in in_scope:
            count_node = scan_node.get_node(f".vulnerabilities.{severity}")
            if count_node.exists() and count_node.get_value() > 0:
                fail_message = (
                    f"{severity.capitalize()} container vulnerabilities detected "
                    f"({count_node.get_value()} found)"
                )
                break

    if fail_message is not None:
        # Records only cover findings with no fix, which ignore_unfixable already
        # drops; skipping the lookup keeps the check from waiting on them.
        records = [] if ignore_unfixable else load_records(c)
        findings, exempted = _collect_findings(scan_node, set(in_scope), exemptions, records)
        if ignore_unfixable:
            # Narrow the failure to findings that carry an upgrade target, so
            # an unfixable base-image CVE cannot hold a release gate closed
            # forever. Deliberately applied *after* the summary/count path has
            # already decided this is a failure: the option can only suppress
            # a failure, never create one.
            if not findings and not exempted:
                # Summary-only scan: fixability is not knowable per finding.
                # `.container_scan.summary.all_fixable` cannot answer this —
                # it is a single boolean across *all* severities, not the
                # in-scope ones. Fail as if the option were off, and say why
                # rather than passing on data we do not have.
                fail_message += (
                    " (ignore_unfixable is set, but the scanner reported no per-finding "
                    "detail, so fixability could not be verified)"
                )
            else:
                in_scope_count = len(findings) + len(exempted)
                # An unfixable finding would not have failed, so exempting it
                # changed nothing worth reporting.
                exempted = [f for f in exempted if f["fixable"]]
                fixable = [f for f in findings if f["fixable"]]
                if not fixable:
                    if exempted:
                        return None, [], (
                            f"{len(exempted)} finding(s) at or above '{min_severity}' with "
                            f"an available fix, all exempted by {_exempted_by(exempted)} — "
                            f"{format_exemptions([f['exemption'] for f in exempted])}"
                        )
                    # Every in-scope finding is unfixable — nothing actionable
                    # to gate on. They remain in the component JSON.
                    print(
                        f"[ignore_unfixable] passing: all {in_scope_count} finding(s) at or "
                        f"above '{min_severity}' have no fix available",
                        file=sys.stderr,
                    )
                    return None, [], None
                findings = fixable
                severity = _most_severe(findings)
                fail_message = (
                    f"{severity.capitalize()} container vulnerabilities with an available fix "
                    f"detected (findings with no available fix ignored)"
                )
        elif exempted:
            if not findings:
                return None, [], (
                    f"{len(exempted)} finding(s) at or above '{min_severity}', all exempted "
                    f"by {_exempted_by(exempted)} — {format_exemptions([f['exemption'] for f in exempted])}"
                )
            # The summary's headline may name a severity only exempt findings had.
            fail_message = (
                f"{_most_severe(findings).capitalize()} container vulnerabilities detected"
            )
        if exempted:
            fail_message += _exempted_suffix(exempted)

        # Multiple failing assertions on a single check — same treatment as
        # the `sca` policy: the headline first (the threshold that tripped
        # plus any `ignore_unfixable` narrowing), then one assertion per
        # offending package/CVE, most severe first. The hub renders each as
        # its own line and truncates the *display* (hub/poster
        # maxAssertionListSize); no policy-side cap or "+N more" tail. A
        # summary-only scan emits the headline alone.
        return fail_message, findings, None

    # Scan data exists but reports no findings/summary — that's a collector
    # bug; raise ValueError deliberately so it surfaces as a crash.
    has_any_data = False
    for severity in in_scope:
        if scan_node.get_node(f".summary.has_{severity}").exists():
            has_any_data = True
            break
        if scan_node.get_node(f".vulnerabilities.{severity}").exists():
            has_any_data = True
            break

    if not has_any_data:
        raise ValueError(
            "Vulnerability counts not available. Ensure collector reports .container_scan.vulnerabilities or .container_scan.summary."
        )

    return None, [], None


def main(node=None):
    c = Check("max-severity", "No findings at or above severity threshold", node=node)
    with c:
        # Parsed before any data is read: a malformed list must fail the check
        # rather than exempt anything.
        exemptions = parse_exempt_findings(variable_or_default("exempt_findings", ""))

        containers = c.get_node(".containers")
        if not containers.exists():
            c.skip("No container definitions detected in this component")

        min_severity = variable_or_default("min_severity", "high").lower()

        if min_severity not in SEVERITY_ORDER:
            raise ValueError(
                f"Policy misconfiguration: 'min_severity' must be one of {SEVERITY_ORDER}, got '{min_severity}'"
            )

        scan_node = c.get_node(".container_scan")
        if not scan_node.exists():
            # The CI tracer materializes `.containers` on almost any build — a
            # bare `docker info` is enough — so its presence does not mean an
            # image shipped. With no pushed ref there is no image to carry
            # CVEs; `executed` is the check that gates whether a scan was owed.
            refs = pushed_image_refs(containers)
            if not refs:
                c.skip("No container image was pushed at this commit — nothing to scan")
            for reason in no_scan_data_reasons(refs):
                c.fail(reason)
            return c

        in_scope = _severities_in_scope(min_severity)
        ignore_unfixable = (
            variable_or_default("ignore_unfixable", "false").strip().lower() == "true"
        )

        messages, findings, skipped = [], [], []
        for scan in _scan_snapshots(c):
            message, current_findings, skip_message = _evaluate_scan(
                c, Node.from_component_json(scan, bundle_info={"workflows_finished": True}),
                in_scope, min_severity,
                ignore_unfixable, exemptions,
            )
            if message:
                messages.append(message)
                findings.extend(current_findings)
            if skip_message:
                skipped.append(skip_message)

        if messages:
            for message in dict.fromkeys(messages):
                c.fail(message)
            for finding in sorted(_dedupe_findings(findings), key=_rank):
                c.fail(finding_text(finding))
        elif skipped:
            c.skip("; ".join(dict.fromkeys(skipped)))

    return c


if __name__ == "__main__":
    main()
