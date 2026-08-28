"""Unit tests for the container-scan max-severity per-CVE failure output
(max_severity.py).

Run from this directory:
    python3 -m unittest test_max_severity -v

These prove the check emits one failing assertion per offending package/CVE —
mirroring the `sca` policy — with severity filtering, most-severe-first
ordering, no policy-side cap (the hub truncates the display), and graceful
degradation to a headline-only failure when the collector emitted no
per-finding detail.
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

# The shape that motivated `ignore_unfixable` (ENG-1571): every critical comes
# from the base image and no fix has shipped upstream, so a release gate on
# critical can never be satisfied by anything the component itself does.
CS_ALL_UNFIXABLE = {
    "source": {"tool": "grype", "integration": "after-json"},
    "image": "registry.example.com/app:1.2.3",
    "vulnerabilities": {"critical": 3, "high": 0, "medium": 0, "low": 0, "total": 3},
    "findings": [
        {"severity": "critical", "package": "curl", "version": "8.14.1-2+deb13u4",
         "ecosystem": "deb", "cve": "CVE-2026-1000", "fix_version": None, "fixable": False},
        {"severity": "critical", "package": "perl", "version": "5.40.1-6",
         "ecosystem": "deb", "cve": "CVE-2026-1001", "fix_version": None, "fixable": False},
        {"severity": "critical", "package": "libc6", "version": "2.41-12",
         "ecosystem": "deb", "cve": "CVE-2026-1002", "fix_version": None, "fixable": False},
    ],
    "summary": {"has_critical": True, "has_high": False, "all_fixable": False},
}

# Summary reports a critical, but the only finding carrying a fix is a high — the
# headline must name the severity of what is actually actionable, not `critical`.
CS_CRIT_UNFIXABLE_HIGH_FIXABLE = {
    "source": {"tool": "trivy", "integration": "after-json"},
    "vulnerabilities": {"critical": 1, "high": 1, "medium": 0, "low": 0, "total": 2},
    "findings": [
        {"severity": "critical", "package": "openssl", "version": "3.5.6-r0",
         "ecosystem": "deb", "cve": "CVE-2026-2000", "fix_version": None, "fixable": False},
        {"severity": "high", "package": "libxml2", "version": "2.13.4",
         "ecosystem": "deb", "cve": "CVE-2026-2001", "fix_version": "2.13.5", "fixable": True},
    ],
    "summary": {"has_critical": True, "has_high": True, "all_fixable": False},
}

# trivy and grype both write `.container_scan` for the same image and the hub
# concatenates their `findings[]`, so the same (severity, package, cve) appears
# twice — and the two scanners can disagree about fixability.
CS_DOUBLE_WRITTEN = {
    "source": {"tool": "grype", "integration": "after-json"},
    "vulnerabilities": {"critical": 1, "high": 0, "medium": 0, "low": 0, "total": 1},
    "findings": [
        {"severity": "critical", "package": "openssl", "version": "3.5.6-r0",
         "ecosystem": "deb", "cve": "CVE-2026-3000", "fix_version": None, "fixable": False},
        {"severity": "critical", "package": "openssl", "version": "3.5.6-r0",
         "ecosystem": "deb", "cve": "CVE-2026-3000", "fix_version": "3.5.7-r0", "fixable": True},
    ],
    "summary": {"has_critical": True, "has_high": False, "all_fixable": False},
}

# No `fixable` key at all (an older blob): fixability must be derived from
# `fix_version`, the same way every scanner collector computes the flag.
CS_NO_FIXABLE_KEY = {
    "source": {"tool": "trivy", "integration": "cicd"},
    "vulnerabilities": {"critical": 2, "high": 0, "medium": 0, "low": 0, "total": 2},
    "findings": [
        {"severity": "critical", "package": "pkg-nofix", "version": "1.0",
         "ecosystem": "deb", "cve": "CVE-2026-4000", "fix_version": None},
        {"severity": "critical", "package": "pkg-hasfix", "version": "1.0",
         "ecosystem": "deb", "cve": "CVE-2026-4001", "fix_version": "1.1"},
    ],
    "summary": {"has_critical": True, "has_high": False},
}


# Two *distinct* advisories in the same package at the same severity, neither
# carrying a CVE id — the case where the dedupe has no identity to merge on.
CS_NO_CVE_ID = {
    "source": {"tool": "grype", "integration": "after-json"},
    "vulnerabilities": {"critical": 2, "high": 0, "medium": 0, "low": 0, "total": 2},
    "findings": [
        {"severity": "critical", "package": "busybox", "version": "1.37.0",
         "ecosystem": "apk", "cve": None, "fix_version": None, "fixable": False},
        {"severity": "critical", "package": "busybox", "version": "1.37.0",
         "ecosystem": "apk", "cve": None, "fix_version": "1.37.1", "fixable": True},
    ],
    "summary": {"has_critical": True, "has_high": False, "all_fixable": False},
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
    """All failure messages a failed max-severity check emitted, joined.

    max-severity emits multiple failing assertions on a single check — the
    severity headline plus one per offending finding — so a test that looks for
    a headline *or* a specific finding line needs the whole set, not just the
    first reason.
    """
    return "\n".join(c.failure_reasons)


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
        reasons = c.failure_reasons
        # Headline assertion + one per in-scope finding — no hand-built sub-list.
        self.assertEqual(len(reasons), 3)   # headline + 2 HIGH (medium below)
        self.assertEqual(reasons[0], "High container vulnerabilities detected")
        joined = "\n".join(reasons)
        self.assertIn("high: github.com/sirupsen/logrus — GHSA-4f99-4q7p-p3gh (fix: 1.9.1)", joined)
        self.assertIn("high: libnghttp2-14 — CVE-2026-58055 (no fix available)", joined)
        # medium is below the `high` threshold — excluded.
        self.assertNotIn("GO-2026-5024", joined)
        # No jargon tail.
        self.assertNotIn("JSON", joined)
        self.assertNotIn("more (", joined)

    def test_orders_most_severe_first(self):
        c = run_check(node(container_scan=CS_MIXED), LUNAR_VAR_min_severity="high")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        reasons = c.failure_reasons
        # Critical sorts before high — it's the first finding assertion, right
        # after the headline.
        self.assertIn("CVE-CRIT", reasons[1])
        joined = "\n".join(reasons)
        self.assertLess(joined.index("CVE-CRIT"), joined.index("CVE-HIGH"))

    def test_summary_only_degrades_to_headline(self):
        c = run_check(node(container_scan=CS_SUMMARY_ONLY), LUNAR_VAR_min_severity="high")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("Critical container vulnerabilities detected", msg)
        # No per-finding detail available -> no enumeration, no crash.
        self.assertNotIn("* ", msg)

    def test_long_finding_list_emits_all_as_assertions(self):
        # No policy-side cap: every finding is its own failing assertion; the
        # hub truncates the display. No "+N more" / "JSON" tail, no sub-list.
        c = run_check(node(container_scan=many_findings(15)), LUNAR_VAR_min_severity="critical")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        reasons = c.failure_reasons
        self.assertEqual(len(reasons), 16)   # headline + all 15, uncapped
        joined = "\n".join(reasons)
        self.assertNotIn("more (", joined)
        self.assertNotIn("JSON", joined)
        self.assertNotIn("\n    * ", joined)

    def test_no_scan_data_fails(self):
        c = run_check(node(container_scan=None))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn("No container scan data found", failure_message(c))

    def test_collapses_findings_double_written_by_two_scanners(self):
        """trivy + grype both writing the same CVE must list it once, not twice."""
        c = run_check(node(container_scan=CS_DOUBLE_WRITTEN), LUNAR_VAR_min_severity="critical")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertEqual(msg.count("CVE-2026-3000"), 1)
        # On a fixability disagreement the fixable entry wins: if any scanner
        # knows of a fix, a fix exists.
        self.assertIn("critical: openssl — CVE-2026-3000 (fix: 3.5.7-r0)", msg)

    def test_never_merges_findings_that_carry_no_cve_id(self):
        """Identity is the CVE id; without one, two findings are not the same one.

        Merging on package+severity alone would collapse distinct advisories —
        and because the fixable entry wins a collision, it would silently drop an
        unfixable finding out of the gate under `ignore_unfixable`. That is the
        one thing the option must never do.
        """
        c = run_check(node(container_scan=CS_NO_CVE_ID), LUNAR_VAR_min_severity="critical")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("critical: busybox (fix: 1.37.1)", msg)
        self.assertIn("critical: busybox (no fix available)", msg)


class IgnoreUnfixableTests(unittest.TestCase):
    """`ignore_unfixable` narrows the failure to findings that have a fix.

    The option may only ever turn a FAIL into a PASS — it is applied after the
    summary/count path has already decided the threshold was crossed, so it can
    never manufacture a failure that the default would not have raised.
    """

    def test_default_is_unchanged_when_all_unfixable(self):
        """Regression guard: with the option off, unfixable findings still fail."""
        c = run_check(node(container_scan=CS_ALL_UNFIXABLE), LUNAR_VAR_min_severity="critical")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("Critical container vulnerabilities detected", msg)
        self.assertIn("critical: curl — CVE-2026-1000 (no fix available)", msg)
        self.assertNotIn("available fix", msg.split(":")[0])

    def test_passes_when_every_in_scope_finding_is_unfixable(self):
        c = run_check(
            node(container_scan=CS_ALL_UNFIXABLE),
            LUNAR_VAR_min_severity="critical",
            LUNAR_VAR_ignore_unfixable="true",
        )
        self.assertEqual(resolved_status(c), CheckStatus.PASS)

    def test_fails_on_the_fixable_subset_only(self):
        c = run_check(
            node(container_scan=CS_MIXED),
            LUNAR_VAR_min_severity="high",
            LUNAR_VAR_ignore_unfixable="true",
        )
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("Critical container vulnerabilities with an available fix detected", msg)
        self.assertIn("findings with no available fix ignored", msg)
        self.assertIn("critical: pkg-crit — CVE-CRIT (fix: 2.1)", msg)
        # The unfixable high is dropped from the enumeration entirely.
        self.assertNotIn("CVE-HIGH", msg)

    def test_headline_names_the_severity_that_is_actionable(self):
        """Summary says critical, but only a high is fixable -> headline says High."""
        c = run_check(
            node(container_scan=CS_CRIT_UNFIXABLE_HIGH_FIXABLE),
            LUNAR_VAR_min_severity="critical",
            LUNAR_VAR_ignore_unfixable="true",
        )
        # min_severity=critical, and the sole critical is unfixable -> nothing in
        # scope is actionable.
        self.assertEqual(resolved_status(c), CheckStatus.PASS)

        c = run_check(
            node(container_scan=CS_CRIT_UNFIXABLE_HIGH_FIXABLE),
            LUNAR_VAR_min_severity="high",
            LUNAR_VAR_ignore_unfixable="true",
        )
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("High container vulnerabilities with an available fix detected", msg)
        self.assertNotIn("Critical container vulnerabilities", msg)
        self.assertIn("CVE-2026-2001", msg)
        self.assertNotIn("CVE-2026-2000", msg)

    def test_summary_only_scan_still_fails_and_says_why(self):
        """Fixability is unknowable without per-finding detail: fail, don't pass."""
        c = run_check(
            node(container_scan=CS_SUMMARY_ONLY),
            LUNAR_VAR_min_severity="high",
            LUNAR_VAR_ignore_unfixable="true",
        )
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("Critical container vulnerabilities detected", msg)
        self.assertIn("fixability could not be verified", msg)

    def test_clean_scan_still_passes(self):
        c = run_check(
            node(container_scan=CS_CLEAN),
            LUNAR_VAR_min_severity="high",
            LUNAR_VAR_ignore_unfixable="true",
        )
        self.assertEqual(resolved_status(c), CheckStatus.PASS)

    def test_derives_fixability_from_fix_version_when_flag_absent(self):
        c = run_check(
            node(container_scan=CS_NO_FIXABLE_KEY),
            LUNAR_VAR_min_severity="critical",
            LUNAR_VAR_ignore_unfixable="true",
        )
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("CVE-2026-4001", msg)      # has fix_version -> fixable
        self.assertNotIn("CVE-2026-4000", msg)   # no fix_version -> ignored

    def test_option_is_off_for_non_true_values(self):
        for raw in ("false", "", "1", "yes", "TRUE  "):
            with self.subTest(raw=raw):
                c = run_check(
                    node(container_scan=CS_ALL_UNFIXABLE),
                    LUNAR_VAR_min_severity="critical",
                    LUNAR_VAR_ignore_unfixable=raw,
                )
                expected = (
                    CheckStatus.PASS if raw.strip().lower() == "true" else CheckStatus.FAIL
                )
                self.assertEqual(resolved_status(c), expected)


if __name__ == "__main__":
    unittest.main()
