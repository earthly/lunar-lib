"""Unit tests for the tool-agnostic GitOps policies.

These exercise the checks over the normalized `.cd.gitops` view a GitOps
collector (e.g. collectors/argocd) produces, covering the pass / fail / skip
paths and the policy-variable wiring (allow-lists, expected_tag). They guard
against regressions like the gitops-managed check reading tags from a
non-existent env var instead of the Component JSON.
"""

import os
import unittest
from contextlib import contextmanager

from lunar_policy import Node, CheckStatus

import importlib.util
import sys
from pathlib import Path


def load_policy(filename):
    """Load a policy module from its (possibly hyphenated) filename."""
    policy_dir = Path(__file__).parent
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_"), policy_dir / f"{filename}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


check_sync_policy = load_policy("sync_policy")
check_source_repo_allowlist = load_policy("source_repo_allowlist")
check_destination_allowlist = load_policy("destination_allowlist")
check_gitops_managed = load_policy("gitops_managed")


@contextmanager
def policy_vars(**kwargs):
    """Temporarily set LUNAR_VAR_* policy inputs for the duration of a test."""
    saved = {}
    try:
        for key, value in kwargs.items():
            env_key = f"LUNAR_VAR_{key}"
            saved[env_key] = os.environ.get(env_key)
            os.environ[env_key] = value
        yield
    finally:
        for env_key, old in saved.items():
            if old is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = old


def is_skipped(check):
    """The SDK's check.status never returns SKIPPED (a skipped check reports
    PASS); a skip is recorded as a SKIPPED result on the check instead."""
    return any(r.result == CheckStatus.SKIPPED for r in check._results)


def app(
    name="payments",
    path="apps/payments.yaml",
    valid=True,
    project="platform",
    automated=True,
    prune=True,
    self_heal=True,
    repo="https://github.com/org/gitops.git",
    namespace="payments",
):
    """Build one `.cd.gitops.applications[]` record."""
    return {
        "name": name,
        "path": path,
        "valid": valid,
        "kind": "Application",
        "project": project,
        "sync_policy": {"automated": automated, "prune": prune, "self_heal": self_heal},
        "destination": {"namespace": namespace, "server": "https://kubernetes.default.svc"},
        "source_ref": {"repoURL": repo, "path": name, "targetRevision": "HEAD"},
        "images": [f"registry.io/{name}"],
    }


def gitops_data(apps=None, tags=None, integration="code"):
    """Build a Component JSON with a `.cd.gitops` view (and optional catalog tags)."""
    data = {
        "cd": {
            "gitops": {
                "source": {"tool": "argocd", "integration": integration},
                "applications": apps if apps is not None else [app()],
                "projects": [],
            }
        }
    }
    if tags is not None:
        data["catalog"] = {"entity": {"tags": tags}}
    return data


class TestSyncPolicy(unittest.TestCase):
    def test_automated_prune_self_heal_passes(self):
        node = Node.from_component_json(gitops_data())
        self.assertEqual(check_sync_policy(node).status, CheckStatus.PASS)

    def test_missing_self_heal_fails(self):
        node = Node.from_component_json(gitops_data([app(self_heal=False)]))
        check = check_sync_policy(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("automated sync policy", check.failure_reasons[0])

    def test_no_gitops_data_skips(self):
        node = Node.from_component_json({})
        self.assertTrue(is_skipped(check_sync_policy(node)))


class TestSourceRepoAllowlist(unittest.TestCase):
    def test_allowed_repo_passes(self):
        with policy_vars(allowed_source_repos="https://github.com/org/gitops.git"):
            node = Node.from_component_json(gitops_data())
            self.assertEqual(check_source_repo_allowlist(node).status, CheckStatus.PASS)

    def test_disallowed_repo_fails(self):
        with policy_vars(allowed_source_repos="https://github.com/org/other.git"):
            node = Node.from_component_json(gitops_data())
            check = check_source_repo_allowlist(node)
            self.assertEqual(check.status, CheckStatus.FAIL)
            self.assertIn("not in", check.failure_reasons[0])

    def test_empty_allowlist_raises(self):
        with policy_vars(allowed_source_repos=""):
            node = Node.from_component_json(gitops_data())
            with self.assertRaises(ValueError):
                check_source_repo_allowlist(node)

    def test_no_gitops_data_skips(self):
        with policy_vars(allowed_source_repos="https://github.com/org/gitops.git"):
            node = Node.from_component_json({})
            self.assertTrue(is_skipped(check_source_repo_allowlist(node)))


class TestDestinationAllowlist(unittest.TestCase):
    def test_allowed_namespace_passes(self):
        with policy_vars(allowed_destinations="payments,frontend"):
            node = Node.from_component_json(gitops_data())
            self.assertEqual(check_destination_allowlist(node).status, CheckStatus.PASS)

    def test_cluster_qualified_entry_matches_namespace(self):
        with policy_vars(allowed_destinations="prod-cluster/payments"):
            node = Node.from_component_json(gitops_data())
            self.assertEqual(check_destination_allowlist(node).status, CheckStatus.PASS)

    def test_disallowed_namespace_fails(self):
        with policy_vars(allowed_destinations="frontend"):
            node = Node.from_component_json(gitops_data())
            check = check_destination_allowlist(node)
            self.assertEqual(check.status, CheckStatus.FAIL)
            self.assertIn("not in the allow-list", check.failure_reasons[0])


class TestGitopsManaged(unittest.TestCase):
    """Coverage check: inverse skip-vs-fail — absence of GitOps data is the violation."""

    def test_has_gitops_data_passes(self):
        node = Node.from_component_json(gitops_data())
        self.assertEqual(check_gitops_managed(node).status, CheckStatus.PASS)

    def test_no_gitops_data_fails(self):
        """A targeted component with no .cd.gitops is the 'should be on GitOps but isn't' case."""
        node = Node.from_component_json({})
        check = check_gitops_managed(node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("GitOps-managed", check.failure_reasons[0])

    def test_expected_tag_present_in_catalog_enforces(self):
        with policy_vars(expected_tag="production"):
            node = Node.from_component_json({"catalog": {"entity": {"tags": ["production"]}}})
            check = check_gitops_managed(node)
            self.assertEqual(check.status, CheckStatus.FAIL)

    def test_expected_tag_absent_from_catalog_skips(self):
        """Regression: expected_tag must gate on .catalog.entity.tags, not a phantom
        LUNAR_COMPONENT_TAGS env var (which made the check skip unconditionally)."""
        with policy_vars(expected_tag="production"):
            node = Node.from_component_json({"catalog": {"entity": {"tags": ["staging"]}}})
            self.assertTrue(is_skipped(check_gitops_managed(node)))

    def test_expected_tag_present_with_gitops_data_passes(self):
        with policy_vars(expected_tag="production"):
            data = gitops_data(tags=["production"])
            node = Node.from_component_json(data)
            self.assertEqual(check_gitops_managed(node).status, CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()
