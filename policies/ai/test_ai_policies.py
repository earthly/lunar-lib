"""Unit tests for the AI policy checks.

The central regression these guard (ENG-1114): a collector-backed check must
stay PENDING while its collector data has not landed yet (the collection
"interim", bundle ``workflows_finished=False``), and only resolve to FAIL once
collection has finished and the data is genuinely absent
(``workflows_finished=True``). Reading the presence gate with
``get_value_or_default(".", None)`` swallowed the SDK's NoDataError and made
these checks render a spurious ❌ mid-collection; the fix uses ``.exists()``,
which lets NoDataError propagate → PENDING during the interim.

Note: ``Check.status`` collapses SKIPPED/no-assertions to PASS, so we assert
against the resolved status enum (PENDING / FAIL / PASS) for the data paths
each check reads.
"""

import importlib.util
import io
import contextlib
import sys
import unittest
from pathlib import Path

from lunar_policy import Node, CheckStatus


def load_policy(filename):
    """Load a policy module from a (possibly hyphenated) filename."""
    policy_dir = Path(__file__).parent
    modname = filename.replace("-", "_")
    spec = importlib.util.spec_from_file_location(modname, policy_dir / f"{filename}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


def run(main, data, workflows_finished):
    """Run a policy against component data at a given collection state.

    workflows_finished=False models the collection interim; True models a
    completed collection cycle. The check prints its result JSON to stdout —
    suppress it so test output stays readable.
    """
    node = Node.from_component_json(data, bundle_info={"workflows_finished": workflows_finished})
    with contextlib.redirect_stdout(io.StringIO()):
        return main(node).status


# check name -> (module filename, minimal "data present + compliant" blob)
AI_CHECKS = {
    "instruction-file-exists": (
        "instruction_file_exists",
        {"ai": {"instructions": {"root": {"exists": True}, "all": [{"filename": "AGENTS.md"}]}}},
    ),
    "instruction-file-sections": (
        "instruction_file_sections",
        {"ai": {"instructions": {"root": {"exists": True, "sections": ["Project Overview", "Build Commands"]}}}},
    ),
    "instruction-file-length": (
        "instruction_file_length",
        {"ai": {"instructions": {"root": {"exists": True, "lines": 50}, "total_bytes": 2000}}},
    ),
    "canonical-naming": (
        "canonical_naming",
        {"ai": {"instructions": {"root": {"exists": True, "filename": "AGENTS.md"}}}},
    ),
    "code-reviewer": (
        "code_reviewer",
        {"ai": {"code_reviewers": [{"detected": True}]}},
    ),
    "ai-authorship-annotated": (
        "ai_authorship_annotated",
        {"ai": {"authorship": {"total_commits": 0}}},
    ),
    "plans-dir-exists": (
        "plans_dir_exists",
        {"ai": {"plans_dir": {"exists": True}}},
    ),
}


class TestInterimPendingRegression(unittest.TestCase):
    """ENG-1114: collector data absent during the interim must be PENDING, not FAIL."""

    def test_absent_data_pends_during_interim(self):
        for check_name, (module, _present) in AI_CHECKS.items():
            with self.subTest(check=check_name):
                main = load_policy(module)
                status = run(main, {}, workflows_finished=False)
                self.assertEqual(
                    status, CheckStatus.PENDING,
                    f"{check_name}: absent data during collection interim must be PENDING, got {status}",
                )

    def test_absent_data_fails_after_collection(self):
        for check_name, (module, _present) in AI_CHECKS.items():
            with self.subTest(check=check_name):
                main = load_policy(module)
                status = run(main, {}, workflows_finished=True)
                self.assertEqual(
                    status, CheckStatus.FAIL,
                    f"{check_name}: absent data after collection finished must be FAIL, got {status}",
                )

    def test_present_compliant_data_passes(self):
        for check_name, (module, present) in AI_CHECKS.items():
            with self.subTest(check=check_name):
                main = load_policy(module)
                status = run(main, present, workflows_finished=True)
                self.assertEqual(
                    status, CheckStatus.PASS,
                    f"{check_name}: present compliant data must PASS, got {status}",
                )


class TestInstructionFileExists(unittest.TestCase):
    def test_root_instruction_file_passes(self):
        data = {"ai": {"instructions": {"root": {"exists": True}, "all": [{"filename": "CLAUDE.md"}]}}}
        self.assertEqual(run(load_policy("instruction_file_exists"), data, True), CheckStatus.PASS)

    def test_collector_ran_but_no_file_fails(self):
        # ai collector reported (data present) but no instruction file anywhere.
        data = {"ai": {"instructions": {"root": {"exists": False}, "all": []}}}
        self.assertEqual(run(load_policy("instruction_file_exists"), data, True), CheckStatus.FAIL)


class TestInstructionFileSections(unittest.TestCase):
    def test_missing_required_section_fails(self):
        data = {"ai": {"instructions": {"root": {"exists": True, "sections": ["Project Overview"]}}}}
        self.assertEqual(run(load_policy("instruction_file_sections"), data, True), CheckStatus.FAIL)


class TestCanonicalNaming(unittest.TestCase):
    def test_non_canonical_root_fails(self):
        data = {"ai": {"instructions": {"root": {"exists": True, "filename": "CLAUDE.md"}}}}
        self.assertEqual(run(load_policy("canonical_naming"), data, True), CheckStatus.FAIL)


class TestCodeReviewer(unittest.TestCase):
    def test_no_reviewer_detected_fails(self):
        data = {"ai": {"code_reviewers": [{"detected": False}]}}
        self.assertEqual(run(load_policy("code_reviewer"), data, True), CheckStatus.FAIL)


class TestPlansDirExists(unittest.TestCase):
    def test_plans_dir_absent_fails(self):
        data = {"ai": {"plans_dir": {"exists": False}}}
        self.assertEqual(run(load_policy("plans_dir_exists"), data, True), CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
