"""Ensure no findings at or above the configured severity threshold.

When findings cross the threshold the check fails with one assertion per
offending package/CVE (when the collector emitted per-finding detail in
`.container_scan.findings[]`), so the hub renders and truncates the list. This
mirrors the `sca` policy's `max-severity` output so a container-image scan and
a code-level SCA scan read identically in the GitHub check / PR comment.

Set `ignore_unfixable: "true"` to narrow the failure to findings that carry an
upgrade target, so an unfixable base-image CVE cannot hold a gate closed
indefinitely. The default (`"false"`) fails on every finding at or above the
threshold, fixable or not. Unfixable findings are always still recorded in the
component JSON — the option changes the *verdict*, never what is collected.
"""

import sys

from lunar_policy import Check, variable_or_default

SEVERITY_ORDER = ["critical", "high", "medium", "low"]


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
    return head + (f" (fix: {fix})" if fix else " (no fix available)")


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
        elif finding["fixable"] and not out[at[key]]["fixable"]:
            out[at[key]] = finding
    return out


def _collect_findings(scan_node, in_scope):
    """Return findings at/above threshold from `.container_scan.findings[]`.

    Returns [] when the collector did not emit per-finding detail (e.g. a
    summary-only scan) — the failure message then stays the headline alone,
    same as the `sca` policy.
    """
    findings_node = scan_node.get_node(".findings")
    if not findings_node.exists():
        return []
    out = []
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
        out.append(
            {
                "id": finding.get_value_or_default(".cve", None),
                "severity": severity,
                "package": finding.get_value_or_default(".package", None),
                "fix_version": fix_version,
                "fixable": bool(fixable),
            }
        )
    return _dedupe_findings(out)


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


def main(node=None):
    c = Check("max-severity", "No findings at or above severity threshold", node=node)
    with c:
        if not c.get_node(".containers").exists():
            c.skip("No container definitions detected in this component")

        min_severity = variable_or_default("min_severity", "high").lower()

        if min_severity not in SEVERITY_ORDER:
            raise ValueError(
                f"Policy misconfiguration: 'min_severity' must be one of {SEVERITY_ORDER}, got '{min_severity}'"
            )

        scan_node = c.get_node(".container_scan")
        if not scan_node.exists():
            c.fail("No container scan data found. Ensure a scanner (Trivy, Grype, etc.) is configured.")
            return c

        in_scope = _severities_in_scope(min_severity)
        ignore_unfixable = (
            variable_or_default("ignore_unfixable", "false").strip().lower() == "true"
        )

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
            findings = _collect_findings(scan_node, set(in_scope))
            if ignore_unfixable:
                # Narrow the failure to findings that carry an upgrade target, so
                # an unfixable base-image CVE cannot hold a release gate closed
                # forever. Deliberately applied *after* the summary/count path has
                # already decided this is a failure: the option can only suppress
                # a failure, never create one.
                if not findings:
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
                    fixable = [f for f in findings if f["fixable"]]
                    if not fixable:
                        # Every in-scope finding is unfixable — nothing actionable
                        # to gate on. They remain in the component JSON.
                        print(
                            f"[ignore_unfixable] passing: all {len(findings)} finding(s) at or "
                            f"above '{min_severity}' have no fix available",
                            file=sys.stderr,
                        )
                        return c
                    findings = fixable
                    severity = _most_severe(findings)
                    fail_message = (
                        f"{severity.capitalize()} container vulnerabilities with an available fix "
                        f"detected (findings with no available fix ignored)"
                    )

            # Multiple failing assertions on a single check — same treatment as
            # the `sca` policy: the headline first (the threshold that tripped
            # plus any `ignore_unfixable` narrowing), then one assertion per
            # offending package/CVE, most severe first. The hub renders each as
            # its own line and truncates the *display* (hub/poster
            # maxAssertionListSize); no policy-side cap or "+N more" tail. A
            # summary-only scan emits the headline alone.
            c.fail(fail_message)
            for finding in sorted(findings, key=_rank):
                c.fail(finding_text(finding))
            return c

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

    return c


if __name__ == "__main__":
    main()
