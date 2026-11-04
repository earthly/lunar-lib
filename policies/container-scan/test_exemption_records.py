"""Unit tests for exemption records (exemption_records.py): the matcher, how
max-severity honors records, and the unfixable-reviewed check.

Run from this directory:
    python3 -m unittest test_exemption_records -v
"""

import contextlib
import datetime
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunar_policy import CheckStatus, Node  # noqa: E402

import max_severity  # noqa: E402
import unfixable_reviewed  # noqa: E402
from exemption_records import find_record, load_records  # noqa: E402
from test_max_severity import failure_message, lunar_env, resolved_status  # noqa: E402

COMPONENT = "github.com/acme/api"
IMAGE = "registry.example.com/api:1.2.3"
CURL = {"severity": "critical", "package": "curl", "version": "8.14.1-2", "ecosystem": "deb",
        "cve": "CVE-2026-10536", "fix_version": None, "fixable": False, "image": IMAGE}
OPENSSL = {"severity": "critical", "package": "libssl3", "version": "3.5.7-r0", "ecosystem": "apk",
           "cve": "CVE-2026-11111", "fix_version": "3.5.8-r0", "fixable": True, "image": IMAGE}
PERL = {"severity": "high", "package": "perl", "version": "5.40.2-r0", "ecosystem": "apk",
        "cve": "CVE-2026-8376", "fix_version": None, "fixable": False, "image": IMAGE}


def scan(*findings):
    severities = [f["severity"] for f in findings]
    return {
        "source": {"tool": "grype", "integration": "code"},
        "vulnerabilities": {s: severities.count(s) for s in ("critical", "high", "medium", "low")},
        "summary": {"has_critical": "critical" in severities, "has_high": "high" in severities},
        "findings": list(findings),
    }


def record(cve, component=COMPONENT, until="2099-01-01"):
    return {"cve": cve, "component": component, "reason": "No fix upstream.", "until": until}


def node(container_scan=None, records=None):
    data = {"containers": {"native": {"docker": {"cicd": {"cmds": []}}}}}
    if container_scan is not None:
        data["container_scan"] = container_scan
    if records is not None:
        data["compliance"] = {"vulnerability_exemptions": {"records": records}}
    return Node.from_component_json(data, bundle_info={"workflows_finished": True})


def run(module, n, **env):
    env.setdefault("LUNAR_COMPONENT_ID", COMPONENT)
    with lunar_env(**env):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return module.main(node=n)


def skip_reason(c):
    return next(r.failure_message for r in c._results if r.result == CheckStatus.SKIPPED)


class LoadRecordsTest(unittest.TestCase):
    TODAY = datetime.date(2026, 11, 4)

    def load(self, records, component=COMPONENT):
        check = node(records=records)
        return load_records(check, component=component, today=self.TODAY)

    def test_keeps_this_components_current_records(self):
        self.assertEqual([r.cve for r in self.load([record("CVE-1")])], ["CVE-1"])

    def test_drops_other_components_expired_and_malformed(self):
        records = [
            record("CVE-OTHER", component="github.com/acme/web"),
            record("CVE-EXPIRED", until="2026-11-03"),
            record("CVE-BAD-DATE", until="2026-02-30"),
            record("", until="2027-01-01"),
            {"cve": "CVE-NO-UNTIL", "component": COMPONENT},
            "not a record",
        ]
        self.assertEqual(self.load(records), [])

    def test_until_day_itself_still_applies(self):
        self.assertEqual(len(self.load([record("CVE-1", until="2026-11-04")])), 1)

    def test_repeated_records_collapse(self):
        # import and refresh both write the list, and merged arrays concatenate.
        self.assertEqual(len(self.load([record("CVE-1"), record("cve-1"), record("CVE-1")])), 1)

    def test_no_component_id_applies_nothing(self):
        self.assertEqual(self.load([record("CVE-1")], component=""), [])

    def test_find_record_ignores_case_and_never_covers_a_fix(self):
        records = self.load([record("cve-2026-10536")])
        self.assertIsNotNone(find_record(records, "CVE-2026-10536", fixable=False))
        self.assertIsNone(find_record(records, "CVE-2026-10536", fixable=True))
        self.assertIsNone(find_record(records, None, fixable=False))


class MaxSeverityRecordsTest(unittest.TestCase):
    def test_record_exempts_a_finding_with_no_fix(self):
        c = run(max_severity, node(scan(CURL, OPENSSL), [record("CVE-2026-10536")]),
                LUNAR_VAR_min_severity="critical")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        message = failure_message(c)
        self.assertIn("1 exempted by exemption records: CVE-2026-10536 (until 2099-01-01)", message)
        self.assertIn("CVE-2026-11111", message)
        self.assertNotIn("curl", message)

    def test_all_exempt_skips(self):
        c = run(max_severity, node(scan(CURL), [record("CVE-2026-10536")]),
                LUNAR_VAR_min_severity="critical")
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)
        self.assertIn("all exempted by exemption records", skip_reason(c))

    def test_record_never_covers_a_fixable_finding(self):
        c = run(max_severity, node(scan(OPENSSL), [record("CVE-2026-11111")]),
                LUNAR_VAR_min_severity="critical")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertNotIn("exempted", failure_message(c))

    def test_expired_or_other_component_record_does_not_apply(self):
        for rec in (record("CVE-2026-10536", until="2026-01-01"),
                    record("CVE-2026-10536", component="github.com/acme/web")):
            c = run(max_severity, node(scan(CURL), [rec]), LUNAR_VAR_min_severity="critical")
            self.assertEqual(resolved_status(c), CheckStatus.FAIL, rec)

    def test_input_and_record_exemptions_are_both_named(self):
        c = run(max_severity, node(scan(CURL, OPENSSL, PERL), [record("CVE-2026-10536")]),
                LUNAR_VAR_min_severity="high",
                LUNAR_VAR_exempt_findings="CVE-2026-11111 libssl3@3.5.7-r0")
        self.assertIn("2 exempted by exempt_findings and exemption records", failure_message(c))


class UnfixableReviewedTest(unittest.TestCase):
    def test_skips_without_scan_data(self):
        c = run(unfixable_reviewed, node())
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)

    def test_skips_summary_only_scan(self):
        summary_only = scan(CURL)
        del summary_only["findings"]
        c = run(unfixable_reviewed, node(summary_only))
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)

    def test_fails_once_per_unreviewed_finding_with_no_fix(self):
        c = run(unfixable_reviewed, node(scan(CURL, OPENSSL, PERL)), LUNAR_VAR_min_severity="high")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        reasons = [r.failure_message for r in c._results if r.result == CheckStatus.FAIL]
        self.assertEqual(reasons[0], "2 finding(s) at or above 'high' have no fix and no approved exemption")
        self.assertEqual(len(reasons), 3)
        self.assertIn("critical: curl — CVE-2026-10536 (no fix available)", reasons[1])
        self.assertIn("high: perl — CVE-2026-8376", reasons[2])

    def test_passes_when_every_finding_with_no_fix_is_covered(self):
        c = run(unfixable_reviewed, node(scan(CURL, OPENSSL, PERL), [record("CVE-2026-10536")]),
                LUNAR_VAR_min_severity="high",
                LUNAR_VAR_exempt_findings="CVE-2026-8376 perl@5.40.2-r0")
        self.assertEqual(resolved_status(c), CheckStatus.PASS)

    def test_ignores_findings_below_the_threshold(self):
        c = run(unfixable_reviewed, node(scan(CURL, PERL), [record("CVE-2026-10536")]),
                LUNAR_VAR_min_severity="critical")
        self.assertEqual(resolved_status(c), CheckStatus.PASS)

    def test_a_fix_from_any_scanner_takes_it_out_of_scope(self):
        # grype has no fix, trivy does: max-severity owns it now.
        trivy_copy = dict(CURL, fix_version="8.14.1-3", fixable=True)
        c = run(unfixable_reviewed, node(scan(CURL, trivy_copy)), LUNAR_VAR_min_severity="critical")
        self.assertEqual(resolved_status(c), CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()
