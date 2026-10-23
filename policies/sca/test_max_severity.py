"""Unit tests for the SCA max-severity verdict (max_severity.py), focused on the
`ignore_unfixable` option and the multi-scanner finding dedup.

Run from this directory:
    python3 -m unittest test_max_severity -v

The webhook side of `max-severity` is covered by test_webhook_alert.py; this
module covers what the check *decides* and what it says. `ignore_unfixable`
narrows a failure to findings that carry an upgrade target, so an unfixable
upstream CVE cannot hold a release gate closed indefinitely. It is applied only
after the summary/count path has already decided the threshold was crossed, so
it can turn a FAIL into a PASS but can never manufacture a failure.
"""

import contextlib
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunar_policy import Node, CheckStatus  # noqa: E402

import max_severity  # noqa: E402
from test_webhook_alert import Receiver  # noqa: E402


def node(sca=None, lang=True):
    """Build a policy node mirroring production policy-eval (workflows done)."""
    data = {}
    if lang:
        data["lang"] = {"go": {"version": "1.22"}}
    if sca is not None:
        data["sca"] = sca
    return Node.from_component_json(data, bundle_info={"workflows_finished": True})


# Mixed fixability at the same severity — the everyday case.
SCA_MIXED = {
    "source": {"tool": "trivy", "integration": "code"},
    "vulnerabilities": {"critical": 0, "high": 2, "medium": 0, "low": 0, "total": 2},
    "findings": [
        {"severity": "high", "package": "golang.org/x/net", "version": "0.7.0",
         "ecosystem": "gomod", "cve": "CVE-2023-44487", "fix_version": "0.17.0", "fixable": True},
        {"severity": "high", "package": "github.com/docker/docker", "version": "28.5.2",
         "ecosystem": "gomod", "cve": "CVE-2026-9001", "fix_version": None, "fixable": False},
    ],
    "summary": {"has_critical": False, "has_high": True, "all_fixable": False},
}

# The shape that motivated the option (ENG-1004 / ENG-1571): every in-scope
# finding is an unfixable upstream advisory, so `sca-high` is permanently red no
# matter what the component does.
SCA_ALL_UNFIXABLE = {
    "source": {"tool": "trivy", "integration": "code"},
    "vulnerabilities": {"critical": 0, "high": 2, "medium": 0, "low": 0, "total": 2},
    "findings": [
        {"severity": "high", "package": "github.com/docker/docker", "version": "28.5.2",
         "ecosystem": "gomod", "cve": "CVE-2026-9001", "fix_version": None, "fixable": False},
        {"severity": "high", "package": "github.com/docker/cli", "version": "28.5.2",
         "ecosystem": "gomod", "cve": "CVE-2026-9002", "fix_version": None, "fixable": False},
    ],
    "summary": {"has_critical": False, "has_high": True, "all_fixable": False},
}

SCA_CLEAN = {
    "source": {"tool": "trivy", "integration": "code"},
    "vulnerabilities": {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0},
    "findings": [],
    "summary": {"has_critical": False, "has_high": False, "all_fixable": True},
}

# Counts/summary but no per-finding detail (e.g. a summary-only SCA collector).
SCA_SUMMARY_ONLY = {
    "source": {"tool": "snyk", "integration": "github_app"},
    "vulnerabilities": {"critical": 1, "high": 3, "medium": 0, "low": 0, "total": 4},
    "summary": {"has_critical": True, "has_high": True},
}

# trivy and grype both write `.sca` for the same component and the hub
# concatenates their `findings[]`, so one vulnerability appears once per scanner
# — and the two can disagree about fixability.
SCA_DOUBLE_WRITTEN = {
    "source": {"tool": "grype", "integration": "code"},
    "vulnerabilities": {"critical": 0, "high": 1, "medium": 0, "low": 0, "total": 1},
    "findings": [
        {"severity": "high", "package": "golang.org/x/net", "version": "0.7.0",
         "ecosystem": "gomod", "cve": "CVE-2023-44487", "fix_version": None, "fixable": False},
        {"severity": "high", "package": "golang.org/x/net", "version": "0.7.0",
         "ecosystem": "gomod", "cve": "CVE-2023-44487", "fix_version": "0.17.0", "fixable": True},
    ],
    "summary": {"has_critical": False, "has_high": True, "all_fixable": False},
}


# Two *distinct* snyk-only advisories in the same package at the same severity.
# Snyk tracks these by `snyk_id` and emits `cve: null`, so they are only
# distinguishable by identity the dedupe must not assume it has.
SCA_SNYK_NO_CVE = {
    "source": {"tool": "snyk", "integration": "cli"},
    "vulnerabilities": {"critical": 0, "high": 2, "medium": 0, "low": 0, "total": 2},
    "findings": [
        {"severity": "high", "package": "lodash", "version": "4.17.20",
         "ecosystem": "npm", "cve": None, "snyk_id": "SNYK-JS-LODASH-1018905",
         "fix_version": None, "fixable": False},
        {"severity": "high", "package": "lodash", "version": "4.17.20",
         "ecosystem": "npm", "cve": None, "snyk_id": "SNYK-JS-LODASH-590103",
         "fix_version": "4.17.21", "fixable": True},
    ],
    "summary": {"has_critical": False, "has_high": True, "all_fixable": False},
}


@contextlib.contextmanager
def lunar_env(**overrides):
    saved = {k: v for k, v in os.environ.items() if k.startswith("LUNAR_")}
    for k in list(os.environ):
        if k.startswith("LUNAR_"):
            del os.environ[k]
    os.environ["LUNAR_COMPONENT_ID"] = "github.com/acme/api"
    os.environ["LUNAR_COMPONENT_GIT_SHA"] = "abc123"
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
    """Check.status reports a skip as PASS, so detect skip from the result set."""
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


class DedupeTests(unittest.TestCase):
    def test_collapses_findings_double_written_by_two_scanners(self):
        c = run_check(node(sca=SCA_DOUBLE_WRITTEN), LUNAR_VAR_min_severity="high")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertEqual(msg.count("CVE-2023-44487"), 1)
        # On a fixability disagreement the fixable entry wins: if any scanner
        # knows of a fix, a fix exists.
        self.assertIn("high: golang.org/x/net — CVE-2023-44487 (fix: 0.17.0)", msg)


    def test_never_merges_findings_that_carry_no_cve_id(self):
        """Identity is the CVE id; without one, two findings are not the same one.

        Snyk emits `cve: null` for snyk-only advisories. Merging those on
        package+severity would collapse distinct vulnerabilities into one and —
        because the fixable entry wins a collision — silently drop an unfixable
        finding out of the gate under `ignore_unfixable`. That is the one thing
        the option must never do.
        """
        c = run_check(node(sca=SCA_SNYK_NO_CVE), LUNAR_VAR_min_severity="high")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("high: lodash (fix: 4.17.21)", msg)
        self.assertIn("high: lodash (no fix available)", msg)

        # With the option on, the fixable one is still enumerated (and the
        # unfixable one correctly filtered) — but neither was ever silently
        # merged away by the other.
        c = run_check(
            node(sca=SCA_SNYK_NO_CVE),
            LUNAR_VAR_min_severity="high",
            LUNAR_VAR_ignore_unfixable="true",
        )
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn("high: lodash (fix: 4.17.21)", failure_message(c))


class IgnoreUnfixableTests(unittest.TestCase):
    def test_default_is_unchanged_when_all_unfixable(self):
        """Regression guard: with the option off, unfixable findings still fail."""
        c = run_check(node(sca=SCA_ALL_UNFIXABLE), LUNAR_VAR_min_severity="high")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("High vulnerability findings detected", msg)
        self.assertIn("high: github.com/docker/docker — CVE-2026-9001 (no fix available)", msg)
        self.assertNotIn("available fix", msg.split(":")[0])

    def test_passes_when_every_in_scope_finding_is_unfixable(self):
        c = run_check(
            node(sca=SCA_ALL_UNFIXABLE),
            LUNAR_VAR_min_severity="high",
            LUNAR_VAR_ignore_unfixable="true",
        )
        self.assertEqual(resolved_status(c), CheckStatus.PASS)

    def test_fails_on_the_fixable_subset_only(self):
        c = run_check(
            node(sca=SCA_MIXED),
            LUNAR_VAR_min_severity="high",
            LUNAR_VAR_ignore_unfixable="true",
        )
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("High vulnerability findings with an available fix detected", msg)
        self.assertIn("findings with no available fix ignored", msg)
        self.assertIn("high: golang.org/x/net — CVE-2023-44487 (fix: 0.17.0)", msg)
        self.assertNotIn("CVE-2026-9001", msg)

    def test_summary_only_scan_still_fails_and_says_why(self):
        """Fixability is unknowable without per-finding detail: fail, don't pass.

        `.sca.summary.all_fixable` cannot stand in — it is a single boolean over
        *all* severities, so it cannot answer whether the in-scope findings are
        fixable.
        """
        c = run_check(
            node(sca=SCA_SUMMARY_ONLY),
            LUNAR_VAR_min_severity="high",
            LUNAR_VAR_ignore_unfixable="true",
        )
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        msg = failure_message(c)
        self.assertIn("Critical vulnerability findings detected", msg)
        self.assertIn("fixability could not be verified", msg)

    def test_clean_scan_still_passes(self):
        c = run_check(
            node(sca=SCA_CLEAN),
            LUNAR_VAR_min_severity="high",
            LUNAR_VAR_ignore_unfixable="true",
        )
        self.assertEqual(resolved_status(c), CheckStatus.PASS)

    def test_skip_and_no_data_paths_are_untouched(self):
        c = run_check(
            node(sca=SCA_ALL_UNFIXABLE, lang=False), LUNAR_VAR_ignore_unfixable="true"
        )
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)

        c = run_check(node(sca=None), LUNAR_VAR_ignore_unfixable="true")
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn("No SCA scanning data found", failure_message(c))


class AlertStaysConsistentWithVerdictTests(unittest.TestCase):
    """The webhook must carry exactly the findings the check failed on.

    `_fire_alert`'s contract is that the alert and the check result never
    diverge, so with `ignore_unfixable` on the payload must be the filtered set —
    otherwise a consumer would be paged about a CVE the gate deliberately let
    through.
    """

    def test_webhook_carries_only_the_fixable_findings(self):
        with Receiver() as r:
            c = run_check(
                node(sca=SCA_MIXED),
                LUNAR_VAR_min_severity="high",
                LUNAR_VAR_ignore_unfixable="true",
                LUNAR_VAR_alert_url=r.url,
            )
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertEqual(len(r.requests), 1)
        _, body = r.requests[0]
        self.assertEqual([f["id"] for f in body["findings"]], ["CVE-2023-44487"])
        self.assertIn("an available fix", body["message"])
        self.assertNotIn("CVE-2026-9001", json.dumps(body))

    def test_no_webhook_when_the_option_suppresses_the_failure(self):
        """A suppressed failure is a PASS — nothing to alert on."""
        with Receiver() as r:
            c = run_check(
                node(sca=SCA_ALL_UNFIXABLE),
                LUNAR_VAR_min_severity="high",
                LUNAR_VAR_ignore_unfixable="true",
                LUNAR_VAR_alert_url=r.url,
            )
        self.assertEqual(resolved_status(c), CheckStatus.PASS)
        self.assertEqual(r.requests, [])


if __name__ == "__main__":
    unittest.main()
