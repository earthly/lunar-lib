"""Ensure no findings at or above the configured severity threshold.

When findings cross the threshold the check fails with one assertion per
offending package/CVE (when the collector emitted per-finding detail), so the
hub renders and truncates the list rather than the policy hand-capping it.

Set `ignore_unfixable: "true"` to narrow the failure to findings that carry an
upgrade target, so an unfixable base-image or upstream CVE cannot hold a gate
closed indefinitely. The default (`"false"`) fails on every finding at or above
the threshold, fixable or not. Unfixable findings are always still recorded in
the component JSON — the option changes the *verdict*, never what is collected.

Additionally, if an `alert_url` input is configured, a best-effort
webhook is POSTed describing the findings (payload schema in webhook.py).
Delivery is fire-and-forget with a short timeout: a slow or unreachable
endpoint never changes the check result — a failing check stays FAILED, it does
not become an ERROR. Leave `alert_url` unset (the default) to disable alerting.
"""

import os
import sys

from lunar_policy import Check, variable_or_default

import webhook

SEVERITY_ORDER = ["critical", "high", "medium", "low"]


def _severities_in_scope(min_severity):
    return SEVERITY_ORDER[: SEVERITY_ORDER.index(min_severity) + 1]


def _dedupe_findings(findings):
    """Collapse the same vulnerability reported by more than one scanner.

    Several scanners can write `.sca` for the same component (e.g. trivy and
    grype), and the hub concatenates their `findings[]` while keeping a single
    writer's counts — so one vulnerability appears once per scanner. Enumerating
    those raw repeats identical lines in the PR comment and inflates the
    "+N more" tail.

    The CVE id *is* the identity, so a finding without one is never merged: snyk
    reports snyk-only advisories with `cve: null`, and collapsing those on
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


def _collect_findings(sca_node, in_scope):
    """Return findings at/above threshold from .sca.findings[], normalized.

    Returns [] when the collector did not emit per-finding detail (e.g. a
    summary-only SCA collector) — the alert still carries the failure message.
    """
    findings_node = sca_node.get_node(".findings")
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
            # available proxy. It is exactly how trivy and snyk compute it, and
            # grype only carries a fix version for findings it marks fixed.
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


def _fire_alert(min_severity, message, findings):
    """Best-effort webhook on failure. Never raises; never changes the result.

    No-op when `alert_url` is unset (alerting disabled). `findings` is the
    already-collected, normalized in-scope list, shared with the failure
    message so the alert and the check result never diverge.
    """
    alert_url = variable_or_default("alert_url", "").strip()
    if not alert_url:
        return
    try:
        payload = webhook.build_payload(
            "sca",
            findings,
            check="max-severity",
            message=message,
            min_severity=min_severity,
        )
        timeout = webhook.positive_float(variable_or_default("alert_timeout_sec", "2"), 2.0)
        auth_token = os.environ.get("LUNAR_SECRET_ALERT_AUTH_TOKEN") or None
        sent, detail = webhook.post_webhook(
            alert_url, payload, timeout=timeout, auth_token=auth_token
        )
        print(
            f"[alert] webhook {'sent' if sent else 'NOT sent'} ({detail}); "
            f"findings={len(findings)} dedupe_key={payload['dedupe_key']}",
            file=sys.stderr,
        )
    except Exception as e:  # noqa: BLE001 - alerting must never break the check
        print(f"[alert] skipped due to error: {type(e).__name__}: {e}", file=sys.stderr)


def main(node=None):
    c = Check("max-severity", "No findings at or above severity threshold", node=node)
    with c:
        if not c.get_node(".lang").exists():
            c.skip("No programming language detected in this component")

        min_severity = variable_or_default("min_severity", "high").lower()

        if min_severity not in SEVERITY_ORDER:
            raise ValueError(
                f"Policy misconfiguration: 'min_severity' must be one of {SEVERITY_ORDER}, got '{min_severity}'"
            )

        sca_node = c.get_node(".sca")
        if not sca_node.exists():
            c.fail("No SCA scanning data found. Ensure a scanner (Snyk, Semgrep, etc.) is configured.")
            return c

        in_scope = _severities_in_scope(min_severity)
        ignore_unfixable = (
            variable_or_default("ignore_unfixable", "false").strip().lower() == "true"
        )

        # Determine the failing severity: summary booleans first (preferred),
        # then counts. Build the same human-readable message we fail with.
        fail_message = None
        for severity in in_scope:
            summary = sca_node.get_node(f".summary.has_{severity}")
            if summary.exists() and summary.get_value():
                fail_message = f"{severity.capitalize()} vulnerability findings detected"
                break
        if fail_message is None:
            for severity in in_scope:
                count_node = sca_node.get_node(f".vulnerabilities.{severity}")
                if count_node.exists() and count_node.get_value() > 0:
                    fail_message = (
                        f"{severity.capitalize()} vulnerability findings detected "
                        f"({count_node.get_value()} found)"
                    )
                    break

        if fail_message is not None:
            findings = _collect_findings(sca_node, set(in_scope))
            if ignore_unfixable:
                # Narrow the failure to findings that carry an upgrade target, so
                # an unfixable upstream CVE cannot hold a release gate closed
                # forever. Deliberately applied *after* the summary/count path
                # has already decided this is a failure: the option can only
                # suppress a failure, never create one.
                if not findings:
                    # Summary-only scan: fixability is not knowable per finding.
                    # `.sca.summary.all_fixable` cannot answer this — it is a
                    # single boolean across *all* severities, not the in-scope
                    # ones. Fail as if the option were off, and say why rather
                    # than passing on data we do not have.
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
                        f"{severity.capitalize()} vulnerability findings with an available fix "
                        f"detected (findings with no available fix ignored)"
                    )

            _fire_alert(min_severity, fail_message, findings)
            # Multiple failing assertions on a single check (the product's
            # shape): the headline first — it names the threshold that tripped
            # and any `ignore_unfixable` narrowing — then one assertion per
            # offending package/CVE, most severe first. The hub renders each as
            # its own line and truncates the *display* (hub/poster
            # maxAssertionListSize), so there is no policy-side cap or
            # "+N more" tail. A summary-only collector emits the headline alone.
            c.fail(fail_message)
            for finding in sorted(findings, key=_rank):
                c.fail(webhook.finding_text(finding))
            return c

        # Scan data exists but reports no findings/summary — that's a collector
        # bug; raise ValueError deliberately so it surfaces.
        has_any_data = False
        for severity in in_scope:
            if sca_node.get_node(f".summary.has_{severity}").exists():
                has_any_data = True
                break
            if sca_node.get_node(f".vulnerabilities.{severity}").exists():
                has_any_data = True
                break

        if not has_any_data:
            raise ValueError(
                "Vulnerability counts not available. Ensure collector reports .sca.vulnerabilities or .sca.summary."
            )

    return c


if __name__ == "__main__":
    main()
