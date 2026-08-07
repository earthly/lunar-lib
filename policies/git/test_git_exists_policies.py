"""Unit tests for the git presence-check policies (pre-commit / gitattributes).

Regression guard for ENG-1114: while the git collector data has not landed yet
(collection interim, ``workflows_finished=False``), these checks must stay
PENDING rather than render a spurious ❌. They only FAIL once collection has
finished and the file is genuinely absent (``workflows_finished=True``).
"""

import importlib.util
import io
import contextlib
import sys
import unittest
from pathlib import Path

from lunar_policy import Node, CheckStatus


def load_policy(filename):
    policy_dir = Path(__file__).parent
    modname = filename.replace("-", "_")
    spec = importlib.util.spec_from_file_location(modname, policy_dir / f"{filename}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


def run(main, data, workflows_finished):
    node = Node.from_component_json(data, bundle_info={"workflows_finished": workflows_finished})
    with contextlib.redirect_stdout(io.StringIO()):
        return main(node).status


# check filename -> "present" compliant blob
GIT_EXISTS_CHECKS = {
    "pre-commit-config-exists": {"git": {"pre_commit": {"repos": [{"repo": "x"}]}}},
    "gitattributes-exists": {"git": {"attributes": {"rules": ["* text=auto"]}}},
}


class TestInterimPendingRegression(unittest.TestCase):
    def test_absent_data_pends_during_interim(self):
        for filename, _present in GIT_EXISTS_CHECKS.items():
            with self.subTest(check=filename):
                status = run(load_policy(filename), {}, workflows_finished=False)
                self.assertEqual(
                    status, CheckStatus.PENDING,
                    f"{filename}: absent data during collection interim must be PENDING, got {status}",
                )

    def test_absent_data_fails_after_collection(self):
        for filename, _present in GIT_EXISTS_CHECKS.items():
            with self.subTest(check=filename):
                status = run(load_policy(filename), {}, workflows_finished=True)
                self.assertEqual(
                    status, CheckStatus.FAIL,
                    f"{filename}: absent data after collection finished must be FAIL, got {status}",
                )

    def test_present_data_passes(self):
        for filename, present in GIT_EXISTS_CHECKS.items():
            with self.subTest(check=filename):
                status = run(load_policy(filename), present, workflows_finished=True)
                self.assertEqual(
                    status, CheckStatus.PASS,
                    f"{filename}: present data must PASS, got {status}",
                )


if __name__ == "__main__":
    unittest.main()
