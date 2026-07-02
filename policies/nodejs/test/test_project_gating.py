"""Regression tests for project-detection gating of the Node.js policy.

Background: a 'backend' component that merely ran `npm`/`node` in CI (no
package.json, so the code collector never set `.project_exists`) was getting
the full Node.js policy applied to it — producing spurious "no lockfile" /
"engines not pinned" style failures on a component that isn't a Node project.

The fix gates the project-structure checks on `.lang.nodejs.project_exists`
while leaving the CI runtime-version check (`min-node-version-cicd`) ungated:
seeing `node` in CI is enough to enforce a minimum CI runtime, no project file
required.

These tests assert that contract from both directions.

Note on assertions: lunar_policy's ``Check.status`` collapses a skipped check
to ``PASS`` (the ``status`` property only distinguishes ERROR/PENDING/FAIL/PASS),
so "did this check skip?" is asserted against the recorded skip result, via the
``_skipped`` helper, rather than against ``status``.
"""

import os
import sys
import unittest

# The check modules live in ../checks (no package __init__), import them flatly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "checks"))

from lunar_policy import Node, CheckStatus  # noqa: E402

from lockfile_exists import check_lockfile_exists  # noqa: E402
from typescript_configured import check_typescript_configured  # noqa: E402
from engines_pinned import check_engines_pinned  # noqa: E402
from min_node_version import check_min_node_version  # noqa: E402
from min_node_version_cicd import check_min_node_version_cicd  # noqa: E402


def _node(data):
    # workflows_finished=True models the realistic state in which a policy is
    # evaluated: collection is complete, so a missing path is *definitively*
    # absent (Node.exists() -> False) rather than "data may still be arriving"
    # (which yields PENDING). This is what lets the project_exists guard resolve
    # to a clean skip.
    return Node.from_component_json(data, bundle_info={"workflows_finished": True})


def _skipped(check):
    """True iff the check recorded a skip (its only result is a skip)."""
    return bool(check._results) and all(
        r.result == CheckStatus.SKIPPED for r in check._results
    )


# A component that ran node/npm in CI but is NOT a Node project: the code
# collector never ran, so `.lang.nodejs` exists (set by the CI collectors) but
# carries no `project_exists` and no project-structure fields.
CI_ONLY = {
    "lang": {
        "nodejs": {
            "cicd": {"cmds": [{"cmd": "node scripts/build.js", "version": "16.20.0"}]},
            "npm": {"cicd": {"cmds": [{"cmd": "npm ci", "version": "8.19.0"}]}},
            "source": {"tool": "node", "integration": "ci"},
        }
    }
}

# Same shape, but the CI node runtime is modern (>= default minimum of 18).
CI_ONLY_MODERN = {
    "lang": {
        "nodejs": {
            "cicd": {"cmds": [{"cmd": "node scripts/build.js", "version": "20.11.0"}]},
            "source": {"tool": "node", "integration": "ci"},
        }
    }
}

# A genuine Node project: the code collector ran and set project_exists.
REAL_PROJECT = {
    "lang": {
        "nodejs": {
            "project_exists": True,
            "package_json_exists": True,
            "package_lock_exists": True,
            "yarn_lock_exists": False,
            "pnpm_lock_exists": False,
            "tsconfig_exists": True,
            "engines_node": ">=18",
            "version": "20.11.0",
            "cicd": {"cmds": [{"cmd": "node scripts/build.js", "version": "16.20.0"}]},
            "source": {"tool": "node", "integration": "code"},
        }
    }
}


class TestProjectStructureChecksSkipWithoutProject(unittest.TestCase):
    """Project-structure checks must SKIP (never FAIL) when there's no project."""

    def test_lockfile_exists_skips(self):
        c = check_lockfile_exists(node=_node(CI_ONLY))
        self.assertTrue(_skipped(c))
        self.assertNotEqual(c.status, CheckStatus.FAIL)

    def test_typescript_configured_skips(self):
        c = check_typescript_configured(node=_node(CI_ONLY))
        self.assertTrue(_skipped(c))
        self.assertNotEqual(c.status, CheckStatus.FAIL)

    def test_engines_pinned_skips(self):
        c = check_engines_pinned(node=_node(CI_ONLY))
        self.assertTrue(_skipped(c))
        self.assertNotEqual(c.status, CheckStatus.FAIL)

    def test_min_node_version_skips(self):
        c = check_min_node_version(node=_node(CI_ONLY))
        self.assertTrue(_skipped(c))
        self.assertNotEqual(c.status, CheckStatus.FAIL)


class TestCiVersionCheckStaysUngated(unittest.TestCase):
    """min-node-version-cicd must fire on CI runtime alone — no project file."""

    def test_old_ci_runtime_fails_even_without_project(self):
        c = check_min_node_version_cicd(node=_node(CI_ONLY))
        self.assertFalse(_skipped(c))
        self.assertEqual(c.status, CheckStatus.FAIL)

    def test_modern_ci_runtime_passes_without_project(self):
        c = check_min_node_version_cicd(node=_node(CI_ONLY_MODERN))
        self.assertFalse(_skipped(c))
        self.assertEqual(c.status, CheckStatus.PASS)


class TestRealProjectStillEnforced(unittest.TestCase):
    """On a genuine Node project, the gated checks run (are not skipped)."""

    def test_lockfile_exists_runs_and_passes(self):
        c = check_lockfile_exists(node=_node(REAL_PROJECT))
        self.assertFalse(_skipped(c))
        self.assertEqual(c.status, CheckStatus.PASS)

    def test_typescript_configured_runs_and_passes(self):
        c = check_typescript_configured(node=_node(REAL_PROJECT))
        self.assertFalse(_skipped(c))
        self.assertEqual(c.status, CheckStatus.PASS)

    def test_min_node_version_runs_and_passes(self):
        c = check_min_node_version(node=_node(REAL_PROJECT))
        self.assertFalse(_skipped(c))
        self.assertEqual(c.status, CheckStatus.PASS)

    def test_engines_pinned_runs(self):
        # The gate lets this check through on a real project; its own pass/fail
        # logic is out of scope for these gating tests.
        c = check_engines_pinned(node=_node(REAL_PROJECT))
        self.assertFalse(_skipped(c))

    def test_ci_version_check_runs_on_real_project(self):
        c = check_min_node_version_cicd(node=_node(REAL_PROJECT))
        self.assertFalse(_skipped(c))
        self.assertEqual(c.status, CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
