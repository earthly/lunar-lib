"""Send a best-effort webhook alert when SCA findings cross the threshold.

This is a *notifier*, not a gate: it always resolves to PASS (or SKIPPED) and
never fails the component. Enable it by setting the ``alert_url`` input; when
unset, the check skips immediately with zero network cost.

It fires at most one POST per policy run, and only when there are findings at
or above ``min_severity`` — so a clean component, a component with only
sub-threshold findings, or a policy with alerting disabled all pay nothing. The
webhook condition mirrors the ``max-severity`` check ("are there findings at or
above ``min_severity``?"). The payload carries the matching findings plus a
stable ``dedupe_key`` so re-runs of the same commit can be de-duplicated by the
consumer.

Delivery is intentionally synchronous with a short timeout (default 2s) rather
than backgrounded: a policy process exits as soon as it returns, which would
kill an in-flight background thread. The timeout bounds the added latency, and
any delivery failure is swallowed so the component is never blocked on a slow
or dead endpoint.
"""

import os
import sys

from lunar_policy import Check, variable_or_default

import webhook

SEVERITY_ORDER = ["critical", "high", "medium", "low"]


def _positive_float(raw, default):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _findings_at_or_above(sca_node, min_severity):
    """Return findings at/above ``min_severity`` normalized to the alert schema.

    Returns ``None`` when the collector did not emit ``.sca.findings`` (e.g. a
    summary-only SCA collector), so the caller can distinguish "no per-finding
    detail available" from "no findings in scope".
    """
    severity_index = SEVERITY_ORDER.index(min_severity)
    in_scope = set(SEVERITY_ORDER[: severity_index + 1])

    findings_node = sca_node.get_node(".findings")
    if not findings_node.exists():
        return None

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


def main(node=None):
    c = Check("alert", "Webhook alert for SCA findings (notifier — never gates)", node=node)
    with c:
        if not c.get_node(".lang").exists():
            c.skip("No programming language detected in this component")

        alert_url = variable_or_default("alert_url", "").strip()
        if not alert_url:
            c.skip("Alerting disabled (no alert_url configured)")

        min_severity = variable_or_default("min_severity", "high").lower()
        if min_severity not in SEVERITY_ORDER:
            raise ValueError(
                f"Policy misconfiguration: 'min_severity' must be one of {SEVERITY_ORDER}, got '{min_severity}'"
            )

        sca_node = c.get_node(".sca")
        if not sca_node.exists():
            c.skip("No SCA scan data; nothing to alert on")

        findings = _findings_at_or_above(sca_node, min_severity)
        if findings is None:
            c.skip("Collector did not emit .sca.findings; nothing to alert on")
        if not findings:
            c.skip(f"No findings at or above '{min_severity}'; no alert sent")

        by_severity = {s: 0 for s in SEVERITY_ORDER}
        for f in findings:
            if f["severity"] in by_severity:
                by_severity[f["severity"]] += 1
        summary = {"total": len(findings), "by_severity": by_severity}

        payload = webhook.build_payload("sca", findings, summary=summary)

        timeout = _positive_float(variable_or_default("alert_timeout", "2"), 2.0)
        auth_token = os.environ.get("LUNAR_SECRET_ALERT_AUTH_TOKEN") or None

        sent, detail = webhook.post_webhook(
            alert_url, payload, timeout=timeout, auth_token=auth_token
        )

        # Best-effort: the check always passes. The delivery outcome is logged
        # to stderr for operator visibility rather than gating the component.
        status = "sent" if sent else "NOT sent"
        print(
            f"[alert] webhook {status} ({detail}); "
            f"findings={len(findings)} dedupe_key={payload['dedupe_key']}",
            file=sys.stderr,
        )
    return c


if __name__ == "__main__":
    main()
