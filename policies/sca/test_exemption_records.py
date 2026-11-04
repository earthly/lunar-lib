"""Unit tests for exemption records in the sca policy: how max-severity honors
them and the unfixable-reviewed check. The matcher itself is the same file as
container-scan's and is tested there.

Run from this directory:
    python3 -m unittest test_exemption_records -v
"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunar_policy import CheckStatus, Node  # noqa: E402

import max_severity  # noqa: E402
import unfixable_reviewed  # noqa: E402
from test_max_severity import failure_message, lunar_env, resolved_status  # noqa: E402

COMPONENT = "github.com/acme/api"
NO_FIX = {"severity": "high", "package": "github.com/docker/docker", "version": "28.5.2",
          "ecosystem": "gomod", "cve": "CVE-2026-9001", "fix_version": None, "fixable": False}
FIXABLE = {"severity": "high", "package": "golang.org/x/net", "version": "0.7.0",
           "ecosystem": "gomod", "cve": "CVE-2023-44487", "fix_version": "0.17.0", "fixable": True}


def sca(*findings):
    return {
        "source": {"tool": "trivy", "integration": "code"},
        "vulnerabilities": {"critical": 0, "high": len(findings), "medium": 0, "low": 0},
        "summary": {"has_critical": False, "has_high": bool(findings)},
        "findings": list(findings),
    }


def record(cve, until="2099-01-01"):
    return {"cve": cve, "component": COMPONENT, "reason": "No fix upstream.", "until": until}


def node(sca_data=None, records=None):
    data = {"lang": {"go": {"version": "1.22"}}}
    if sca_data is not None:
        data["sca"] = sca_data
    if records is not None:
        data["compliance"] = {"vulnerability_exemptions": {"records": records}}
    return Node.from_component_json(data, bundle_info={"workflows_finished": True})


def run(module, n, **env):
    env.setdefault("LUNAR_COMPONENT_ID", COMPONENT)
    with lunar_env(**env):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return module.main(node=n)


class MaxSeverityRecordsTest(unittest.TestCase):
    def test_record_exempts_a_finding_with_no_fix(self):
        c = run(max_severity, node(sca(NO_FIX, FIXABLE), [record("cve-2026-9001")]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        message = failure_message(c)
        self.assertIn("1 exempted by exemption records: cve-2026-9001 (until 2099-01-01)", message)
        self.assertNotIn("github.com/docker/docker", message)

    def test_all_exempt_skips(self):
        c = run(max_severity, node(sca(NO_FIX), [record("CVE-2026-9001")]))
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)

    def test_record_never_covers_a_fixable_finding(self):
        c = run(max_severity, node(sca(FIXABLE), [record("CVE-2023-44487")]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertNotIn("exempted", failure_message(c))

    def test_expired_record_does_not_apply(self):
        c = run(max_severity, node(sca(NO_FIX), [record("CVE-2026-9001", until="2026-01-01")]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)

    def test_records_change_nothing_with_ignore_unfixable(self):
        c = run(max_severity, node(sca(NO_FIX), [record("CVE-2026-9001")]), LUNAR_VAR_ignore_unfixable="true")
        self.assertEqual(resolved_status(c), CheckStatus.PASS)


class UnfixableReviewedTest(unittest.TestCase):
    def test_skips_without_scan_data(self):
        self.assertEqual(resolved_status(run(unfixable_reviewed, node())), CheckStatus.SKIPPED)

    def test_fails_on_an_unreviewed_finding_with_no_fix(self):
        c = run(unfixable_reviewed, node(sca(NO_FIX, FIXABLE)))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        reasons = [r.failure_message for r in c._results if r.result == CheckStatus.FAIL]
        self.assertEqual(reasons[0], "1 finding(s) at or above 'high' have no fix and no approved exemption")
        self.assertIn("CVE-2026-9001", reasons[1])
        self.assertEqual(len(reasons), 2)

    def test_passes_when_covered(self):
        c = run(unfixable_reviewed, node(sca(NO_FIX, FIXABLE), [record("CVE-2026-9001")]))
        self.assertEqual(resolved_status(c), CheckStatus.PASS)

    def test_other_component_record_does_not_cover(self):
        c = run(unfixable_reviewed, node(sca(NO_FIX), [record("CVE-2026-9001")]),
                LUNAR_COMPONENT_ID="github.com/acme/web")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
