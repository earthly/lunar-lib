"""Unit tests for the CODEOWNERS repo-boilerplate policies.

Regression guard for ENG-1249 (Barclays POV): the codeowners sub-checks were
gating on a raw ``c.get_value(".ownership.codeowners.exists")``. When the
codeowners collector produced no data for a component, that raises — leaving
the check stuck in a non-terminal state (PENDING during collection, then
ERROR once collection finished, rendered amber "No data at path" forever)
instead of resolving.

The fix mirrors ``codeowners-exists`` and the git presence-check policies:
gate on the workflows-aware ``get_node(...).exists()`` so the check always
resolves to a terminal state — SKIP when there is no CODEOWNERS file
(codeowners-exists owns that failure), PASS/FAIL on the actual content,
and PENDING only while collection is genuinely still running.
"""

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path

from lunar_policy import CheckStatus, Node

# Sub-checks that only apply once a CODEOWNERS file exists. When the file is
# absent these must resolve to SKIP (codeowners-exists carries the failure),
# never get stuck pending/errored.
SUB_CHECKS = [
    "codeowners-catchall",
    "codeowners-valid",
    "codeowners-max-owners",
    "codeowners-min-owners",
    "codeowners-no-empty-rules",
    "codeowners-no-individuals-only",
    "codeowners-team-owners",
]

# A fully compliant CODEOWNERS blob (file exists, valid, catch-all rule,
# two team owners) — every sub-check should PASS against this.
COMPLIANT = {
    "ownership": {
        "codeowners": {
            "exists": True,
            "valid": True,
            "errors": [],
            "owners": ["@org/team-a", "@org/team-b"],
            "team_owners": ["@org/team-a", "@org/team-b"],
            "rules": [
                {
                    "pattern": "*",
                    "owners": ["@org/team-a", "@org/team-b"],
                    "owner_count": 2,
                }
            ],
        }
    }
}

# Per-check blobs that violate exactly that check (file present + parseable).
VIOLATIONS = {
    # No catch-all (*) rule.
    "codeowners-catchall": {
        "rules": [{"pattern": "/src", "owners": ["@org/team-a"], "owner_count": 1}],
    },
    # Invalid syntax.
    "codeowners-valid": {
        "valid": False,
        "errors": [{"line": 3, "message": "invalid owner '@'"}],
    },
    # A rule with more owners than the default max (10).
    "codeowners-max-owners": {
        "rules": [{"pattern": "*", "owners": ["@u"] * 11, "owner_count": 11}],
    },
    # A rule with fewer owners than the default min (2) but not un-assigned (0).
    "codeowners-min-owners": {
        "rules": [{"pattern": "*", "owners": ["@org/team-a"], "owner_count": 1}],
    },
    # A rule that un-assigns ownership (0 owners).
    "codeowners-no-empty-rules": {
        "rules": [{"pattern": "*", "owners": [], "owner_count": 0}],
    },
    # A rule owned only by individuals, no team.
    "codeowners-no-individuals-only": {
        "team_owners": [],
        "rules": [{"pattern": "*", "owners": ["@alice"], "owner_count": 1}],
    },
    # No team owners anywhere.
    "codeowners-team-owners": {
        "team_owners": [],
        "rules": [{"pattern": "*", "owners": ["@alice"], "owner_count": 1}],
    },
}

# Collector produced no ownership data at all (the Barclays symptom).
ABSENT = {}
# Collector ran and found no CODEOWNERS file (exists explicitly false).
NO_FILE = {"ownership": {"codeowners": {"exists": False}}}


def load_policy(filename):
    policy_dir = Path(__file__).parent
    modname = filename.replace("-", "_")
    spec = importlib.util.spec_from_file_location(modname, policy_dir / f"{filename}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


def _compliant_with(overrides):
    blob = {
        "ownership": {"codeowners": dict(COMPLIANT["ownership"]["codeowners"])}
    }
    blob["ownership"]["codeowners"].update(overrides)
    return blob


def run(filename, data, workflows_finished=True):
    main = load_policy(filename)
    node = Node.from_component_json(
        data, bundle_info={"workflows_finished": workflows_finished}
    )
    with contextlib.redirect_stdout(io.StringIO()):
        return main(node)


def observed_status(check):
    # Check.status collapses a pure-skip to PASS, so detect SKIP explicitly.
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


class TestStuckPendingRegression(unittest.TestCase):
    """ENG-1249: absent collector data must resolve to a terminal state."""

    def test_absent_data_resolves_to_skip_after_collection(self):
        # THE core guard: no codeowners data + collection finished must SKIP,
        # never stay amber (PENDING/ERROR "No data at path ...").
        for check in SUB_CHECKS:
            with self.subTest(check=check):
                status = observed_status(run(check, ABSENT, workflows_finished=True))
                self.assertEqual(
                    status,
                    CheckStatus.SKIPPED,
                    f"{check}: absent data after collection must SKIP, got {status}",
                )

    def test_no_file_resolves_to_skip(self):
        # Collector ran and wrote exists=false → sub-checks skip (exists fails).
        for check in SUB_CHECKS:
            with self.subTest(check=check):
                status = observed_status(run(check, NO_FILE, workflows_finished=True))
                self.assertEqual(
                    status,
                    CheckStatus.SKIPPED,
                    f"{check}: no CODEOWNERS file must SKIP, got {status}",
                )

    def test_absent_data_pends_during_collection(self):
        # While collection is still running, absence is not yet a verdict.
        for check in SUB_CHECKS:
            with self.subTest(check=check):
                status = observed_status(run(check, ABSENT, workflows_finished=False))
                self.assertEqual(
                    status,
                    CheckStatus.PENDING,
                    f"{check}: absent data mid-collection must PEND, got {status}",
                )


class TestSubCheckContent(unittest.TestCase):
    """The fix must not regress the actual pass/fail logic."""

    def test_compliant_passes(self):
        for check in SUB_CHECKS:
            with self.subTest(check=check):
                status = observed_status(run(check, COMPLIANT, workflows_finished=True))
                self.assertEqual(
                    status,
                    CheckStatus.PASS,
                    f"{check}: compliant CODEOWNERS must PASS, got {status}",
                )

    def test_violation_fails(self):
        for check, overrides in VIOLATIONS.items():
            with self.subTest(check=check):
                status = observed_status(
                    run(check, _compliant_with(overrides), workflows_finished=True)
                )
                self.assertEqual(
                    status,
                    CheckStatus.FAIL,
                    f"{check}: violating CODEOWNERS must FAIL, got {status}",
                )


class TestCodeownersExists(unittest.TestCase):
    """codeowners-exists owns the file-existence verdict: it FAILS when absent
    (this is the single actionable failure the sub-checks defer to)."""

    def test_absent_after_collection_fails(self):
        status = observed_status(run("codeowners-exists", ABSENT, workflows_finished=True))
        self.assertEqual(status, CheckStatus.FAIL)

    def test_no_file_fails(self):
        status = observed_status(run("codeowners-exists", NO_FILE, workflows_finished=True))
        self.assertEqual(status, CheckStatus.FAIL)

    def test_absent_pends_during_collection(self):
        status = observed_status(run("codeowners-exists", ABSENT, workflows_finished=False))
        self.assertEqual(status, CheckStatus.PENDING)

    def test_present_passes(self):
        status = observed_status(run("codeowners-exists", COMPLIANT, workflows_finished=True))
        self.assertEqual(status, CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()
