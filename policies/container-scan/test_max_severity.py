"""Unit tests for the container-scan max-severity per-CVE failure output
(max_severity.py).

Run from this directory:
    python3 -m unittest test_max_severity -v

These prove the check enumerates the offending packages/CVEs in its failure
message — mirroring the `sca` policy — with severity filtering, most-severe-first
ordering, the MAX_LISTED_FINDINGS cap + "+N more" tail, and graceful degradation
to a headline-only message when the collector emitted no per-finding detail.
"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunar_policy import Node, CheckStatus  # noqa: E402

import max_severity  # noqa: E402


def node(container_scan=None, containers=True):
    """Build a policy node mirroring production policy-eval (workflows done)."""
    data = {}
    if containers:
        # Presence of `.containers` is the applicability gate (written by the
        # docker collector). The exact shape is irrelevant to this check.
        data["containers"] = {"native": {"docker": {"cicd": {"cmds": []}}}}
    if container_scan is not None:
        data["container_scan"] = container_scan
    return Node.from_component_json(data, bundle_info={"workflows_finished": True})


# Grype/Trivy-style: summary has has_critical/has_high; full findings list.
CS_WITH_HIGH = {
    "source": {"tool": "grype", "integration": "cron"},
    "image": "registry.example.com/app:1.2.3",
    "vulnerabilities": {"critical": 0, "high": 2, "medium": 1, "low": 0, "total": 3},
    "findings": [
        {"severity": "high", "package": "github.com/sirupsen/logrus", "version": "1.9.0",
         "ecosystem": "go-module", "cve": "GHSA-4f99-4q7p-p3gh", "fix_version": "1.9.1", "fixable": True},
        {"severity": "high", "package": "libnghttp2-14", "version": "1.69.0-r0",
         "ecosystem": "apk", "cve": "CVE-2026-58055", "fix_version": None, "fixable": False},
        {"severity": "medium", "package": "golang.org/x/sys", "version": "0.1.0",
         "ecosystem": "go-module", "cve": "GO-2026-5024", "fix_version": "0.44.0", "fixable": True},
    ],
    "summary": {"has_critical": False, "has_high": True, "all_fixable": False},
}

CS_MIXED = {
    "source": {"tool": "grype", "integration": "cron"},
    "vulnerabilities": {"critical": 1, "high": 1, "medium": 0, "low": 0, "total": 2},
    "findings": [
        {"severity": "high", "package": "pkg-high", "version": "1.0",
         "ecosystem": "apk", "cve": "CVE-HIGH", "fix_version": None, "fixable": False},
        {"severity": "critical", "package": "pkg-crit", "version": "2.0",
         "ecosystem": "apk", "cve": "CVE-CRIT", "fix_version": "2.1", "fixable": True},
    ],
    "summary": {"has_critical": True, "has_high": True, "all_fixable": False},
}

CS_CLEAN = {
    "source": {"tool": "grype", "integration": "cron"},
    "vulnerabilities": {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0},
    "findings": [],
    "summary": {"has_critical": False, "has_high": False, "all_fixable": True},
}

# A scan that reports counts/summary but no per-finding detail.
CS_SUMMARY_ONLY = {
    "source": {"tool": "snyk", "integration": "ci"},
    "vulnerabilities": {"critical": 1, "high": 3, "medium": 0, "low": 0, "total": 4},
    "summary": {"has_critical": True, "has_high": True},
}


def many_findings(n):
    """A scan result with `n` distinct critical findings (cap-test fixture)."""
    return {
        "source": {"tool": "grype", "integration": "cron"},
        "vulnerabilities": {"critical": n, "high": 0, "medium": 0, "low": 0, "total": n},
        "findings": [
            {"severity": "critical", "package": f"pkg{i:03d}", "version": "1.0.0",
             "ecosystem": "apk", "cve": f"CVE-2026-{i:04d}", "fix_version": "1.0.1", "fixable": True}
            for i in range(n)
        ],
        "summary": {"has_critical": True, "has_high": False},
    }


@contextlib.contextmanager
def lunar_env(**overrides):
    saved = dict(os.environ)
    for k in list(os.environ):
        if k.startswith("LUNAR_"):
            del os.environ[k]
    os.environ.update(overrides)
    try:
        yield
    finally:
        for k in list(os.environ):
            if k.startswith("LUNAR_"):
                del os.environ[k]
        os.environ.update(saved)


def run_check(n, **env):
    with lunar_env(**env):
        with contextlib.redirect_stdout(io.StringIO()):
            return max_severity.main(node=n)


def resolved_status(c):
    for r in getattr(c, "_results", []):
        if r.result == CheckStatus.SKIPPED:
            return CheckStatus.SKIPPED
    return c.status


def failure_message(c):
    reasons = c.failure_reasons
    return reasons[0] if reasons else ""


class FindingTextTests(unittest.TestCase):
    def test_format_matches_sca(self):
        self.assertEqual(
            max_severity.finding_text(
                {"severity": "high", "package": "p", "id": "CVE-1", "fix_version": "1.0"}
            ),
            "high: p — CVE-1 (fix: 1.0)",
        )

    def test_no_fix_available(self):
        self.assertEqual(
            max_severity.finding_text(
                {"severity": "medium", "package": "p", "id": "CVE-2", "fix_version": None}
            ),
            "medium: p — CVE-2 (no fix available)",
        )


class MaxSeverityTests(unittest.TestCase):
    def test_skips_when_no_containers(self):
        c = run_check(node(container_scan=CS_WITH_HIGH, containers=False))
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)

    def test_passes_when_clean(self):
        c = run_check(node(container_scan=CS_CLEAN))
        self.assertEqual(resolved_status(c), CheckStatus.PASS)

    def test_fails_and_enumerates_findings(self):
        c = run_check(node(container_scan=CS_WITH_HIGH), LUNAR_VAR_min_severity="high")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        # Headline preserved, then a Markdown sub-list of the in-scope findings.
        self.assertIn("High container vulnerabilities detected", msg)
        self.assertIn("high: github.com/sirupsen/logrus — GHSA-4f99-4q7p-p3gh (fix: 1.9.1)", msg)
        self.assertIn("high: libnghttp2-14 — CVE-2026-58055 (no fix available)", msg)
        self.assertIn("\n    * ", msg)  # multiline nested-list rendering
        # medium is below the `high` threshold — excluded from the enumeration.
        self.assertNotIn("GO-2026-5024", msg)

    def test_orders_most_severe_first(self):
        c = run_check(node(container_scan=CS_MIXED), LUNAR_VAR_min_severity="high")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertLess(msg.index("CVE-CRIT"), msg.index("CVE-HIGH"))

    def test_summary_only_degrades_to_headline(self):
        c = run_check(node(container_scan=CS_SUMMARY_ONLY), LUNAR_VAR_min_severity="high")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("Critical container vulnerabilities detected", msg)
        # No per-finding detail available -> no enumeration, no crash.
        self.assertNotIn("* ", msg)

    def test_caps_at_ten_with_more_tail(self):
        c = run_check(node(container_scan=many_findings(15)), LUNAR_VAR_min_severity="critical")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertEqual(msg.count("\n    * "), 11)  # 10 findings + the "+N more" tail
        # Surface-agnostic pointer to the JSON (no internal jargon).
        self.assertIn("+5 more (full list in the JSON)", msg)

    def test_no_scan_data_fails(self):
        c = run_check(node(container_scan=None))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn("No container scan data found", failure_message(c))


if __name__ == "__main__":
    unittest.main()
