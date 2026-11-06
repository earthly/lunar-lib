"""Fail on each finding at or above min_severity that has no fix and no approved exemption.

`ignore_unfixable` keeps `max-severity` practical, but it also hides findings
nobody has reviewed. This check names them, one assertion each, until each is
covered by an exemption record or an `exempt_findings` entry. Findings with a
fix are `max-severity`'s job, so they never count here.
"""

import sys

from exemption_records import load_records
from exemptions import parse_exempt_findings
from lunar_policy import Check, variable_or_default
from max_severity import SEVERITY_ORDER, _collect_findings, _rank, _severities_in_scope, finding_text


def main(node=None):
    c = Check(
        "unfixable-reviewed",
        "Every finding with no fix at or above the threshold has an approved exemption",
        node=node,
    )
    with c:
        # Parsed before any data is read: a malformed list must fail the check.
        exemptions = parse_exempt_findings(variable_or_default("exempt_findings", ""))

        min_severity = variable_or_default("min_severity", "high").lower()
        if min_severity not in SEVERITY_ORDER:
            raise ValueError(
                f"Policy misconfiguration: 'min_severity' must be one of {SEVERITY_ORDER}, got '{min_severity}'"
            )

        scan_node = c.get_node(".container_scan")
        if not scan_node.exists():
            c.skip("No container scan data at this commit")
        if not scan_node.get_node(".findings").exists():
            c.skip("The scanner reported no per-finding detail, so findings with no fix can't be identified")

        findings, exempted = _collect_findings(
            scan_node, set(_severities_in_scope(min_severity)), exemptions, load_records(c)
        )
        unreviewed = [f for f in findings if not f["fixable"]]
        reviewed = [f for f in exempted if not f["fixable"]]
        if reviewed:
            print(f"[unfixable-reviewed] {len(reviewed)} finding(s) with no fix have an exemption", file=sys.stderr)
        if unreviewed:
            c.fail(
                f"{len(unreviewed)} finding(s) at or above '{min_severity}' have no fix and no approved exemption"
            )
            for finding in sorted(unreviewed, key=_rank):
                c.fail(finding_text(finding))

    return c


if __name__ == "__main__":
    main()
