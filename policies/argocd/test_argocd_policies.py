"""Unit tests for the ArgoCD-specific policies (schema validity, project hygiene)."""

import os
import unittest
from contextlib import contextmanager

from lunar_policy import Node, CheckStatus

import importlib.util
import sys
from pathlib import Path


def load_policy(filename):
    policy_dir = Path(__file__).parent
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_"), policy_dir / f"{filename}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


check_valid = load_policy("valid")
check_non_default_project = load_policy("non_default_project")


@contextmanager
def policy_vars(**kwargs):
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
    """check.status never returns SKIPPED; a skip is recorded as a SKIPPED result."""
    return any(r.result == CheckStatus.SKIPPED for r in check._results)


def gitops_data(apps=None, projects=None):
    return {
        "cd": {
            "gitops": {
                "source": {"tool": "argocd", "integration": "code"},
                "applications": apps if apps is not None else [],
                "projects": projects if projects is not None else [],
            }
        }
    }


def application(name="payments", valid=True, project="platform"):
    return {"name": name, "path": f"apps/{name}.yaml", "valid": valid, "project": project}


def project(name="platform", valid=True):
    return {"name": name, "path": f"projects/{name}.yaml", "valid": valid, "is_default": name == "default"}


class TestValid(unittest.TestCase):
    def test_all_valid_passes(self):
        data = gitops_data(apps=[application(valid=True)], projects=[project(valid=True)])
        self.assertEqual(check_valid(Node.from_component_json(data)).status, CheckStatus.PASS)

    def test_invalid_application_fails(self):
        data = gitops_data(apps=[application(name="bad", valid=False)])
        check = check_valid(Node.from_component_json(data))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("not a valid argoproj resource", check.failure_reasons[0])

    def test_invalid_project_fails(self):
        data = gitops_data(projects=[project(name="bad", valid=False)])
        self.assertEqual(check_valid(Node.from_component_json(data)).status, CheckStatus.FAIL)

    def test_no_gitops_data_skips(self):
        self.assertTrue(is_skipped(check_valid(Node.from_component_json({}))))


class TestNonDefaultProject(unittest.TestCase):
    def test_scoped_project_passes(self):
        data = gitops_data(apps=[application(project="platform")])
        self.assertEqual(
            check_non_default_project(Node.from_component_json(data)).status, CheckStatus.PASS
        )

    def test_default_project_fails(self):
        data = gitops_data(apps=[application(project="default")])
        check = check_non_default_project(Node.from_component_json(data))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("default", check.failure_reasons[0].lower())

    def test_project_not_in_allowlist_fails(self):
        with policy_vars(allowed_projects="platform,payments"):
            data = gitops_data(apps=[application(project="rogue")])
            check = check_non_default_project(Node.from_component_json(data))
            self.assertEqual(check.status, CheckStatus.FAIL)
            self.assertIn("allow-list", check.failure_reasons[0])

    def test_project_in_allowlist_passes(self):
        with policy_vars(allowed_projects="platform,payments"):
            data = gitops_data(apps=[application(project="platform")])
            self.assertEqual(
                check_non_default_project(Node.from_component_json(data)).status, CheckStatus.PASS
            )

    def test_no_gitops_data_skips(self):
        self.assertTrue(
            is_skipped(check_non_default_project(Node.from_component_json({})))
        )


if __name__ == "__main__":
    unittest.main()
