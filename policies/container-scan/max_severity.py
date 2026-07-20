"""Ensure no findings at or above the configured severity threshold.

When findings cross the threshold the check fails with one assertion per
offending package/CVE (when the collector emitted per-finding detail in
`.container_scan.findings[]`), so the hub renders and truncates the list. This
mirrors the `sca` policy's `max-severity` output so a container-image scan and
a code-level SCA scan read identically in the GitHub check / PR comment.
"""

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
        out.append(
            {
                "id": finding.get_value_or_default(".cve", None),
                "severity": severity,
                "package": finding.get_value_or_default(".package", None),
                "fix_version": finding.get_value_or_default(".fix_version", None),
            }
        )
    return out


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
            if findings:
                # One failing assertion per offending package/CVE (most severe
                # first) — same treatment as the `sca` policy. The hub renders
                # each as its own line and truncates the list for display
                # (hub/poster maxAssertionListSize); no policy-side cap or
                # "+N more" tail. Summary-only scans fall back to the headline.
                for finding in sorted(findings, key=_rank):
                    c.fail(finding_text(finding))
            else:
                c.fail(fail_message)
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
