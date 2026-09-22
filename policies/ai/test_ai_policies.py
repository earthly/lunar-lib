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


def _instructions(all_files, root_lines=50, total_bytes=2000, root_filename="AGENTS.md"):
    return {"ai": {"instructions": {
        "root": {"exists": True, "filename": root_filename, "lines": root_lines, "bytes": 1000},
        "all": all_files,
        "total_bytes": total_bytes,
    }}}


class TestInstructionFileLength(unittest.TestCase):
    """The caps apply to every file in all[], not just the root one."""

    def setUp(self):
        self.main = load_policy("instruction_file_length")

    def test_all_files_within_caps_passes(self):
        data = _instructions([
            {"path": "AGENTS.md", "lines": 50, "bytes": 1000},
            {"path": "pkg/api/AGENTS.md", "lines": 120, "bytes": 4000},
        ])
        self.assertEqual(run(self.main, data, True), CheckStatus.PASS)

    def test_root_over_line_cap_fails(self):
        data = _instructions([{"path": "AGENTS.md", "lines": 900, "bytes": 1000}], root_lines=900)
        self.assertEqual(run(self.main, data, True), CheckStatus.FAIL)

    def test_root_under_min_lines_fails(self):
        data = _instructions([{"path": "AGENTS.md", "lines": 3, "bytes": 100}], root_lines=3)
        self.assertEqual(run(self.main, data, True), CheckStatus.FAIL)

    def test_non_root_file_over_line_cap_fails(self):
        """Root is tidy; a nested AGENTS.md busts the cap. Passed before this check looked at all[]."""
        data = _instructions([
            {"path": "AGENTS.md", "lines": 50, "bytes": 1000},
            {"path": "services/api/AGENTS.md", "lines": 1200, "bytes": 24000},
        ])
        self.assertEqual(run(self.main, data, True), CheckStatus.FAIL)

    def test_tool_file_over_byte_cap_fails(self):
        """total_bytes only sums AGENTS.md, so a huge CLAUDE.md used to sail through."""
        data = _instructions([
            {"path": "AGENTS.md", "lines": 50, "bytes": 1000},
            {"path": "CLAUDE.md", "lines": 40, "bytes": 200000},
        ], total_bytes=1000)
        self.assertEqual(run(self.main, data, True), CheckStatus.FAIL)

    def test_symlinked_alias_over_cap_is_ignored(self):
        """CLAUDE.md -> AGENTS.md is the same file; don't report it twice."""
        data = _instructions([
            {"path": "AGENTS.md", "lines": 50, "bytes": 1000},
            {"path": "CLAUDE.md", "lines": 5000, "bytes": 900000, "is_symlink": True},
        ])
        self.assertEqual(run(self.main, data, True), CheckStatus.PASS)

    def test_no_all_array_falls_back_to_root(self):
        """Older collector data with no all[] still gets the root file capped."""
        data = {"ai": {"instructions": {"root": {"exists": True, "lines": 900, "bytes": 1000}, "total_bytes": 1000}}}
        self.assertEqual(run(self.main, data, True), CheckStatus.FAIL)

    def test_offending_file_is_named_in_the_message(self):
        data = _instructions([
            {"path": "AGENTS.md", "lines": 50, "bytes": 1000},
            {"path": "services/api/AGENTS.md", "lines": 1200, "bytes": 24000},
        ])
        node = Node.from_component_json(data, bundle_info={"workflows_finished": True})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.main(node)
        self.assertIn("services/api/AGENTS.md", buf.getvalue())


class TestPlansDirExists(unittest.TestCase):
    def test_plans_dir_absent_fails(self):
        data = {"ai": {"plans_dir": {"exists": False}}}
        self.assertEqual(run(load_policy("plans_dir_exists"), data, True), CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
