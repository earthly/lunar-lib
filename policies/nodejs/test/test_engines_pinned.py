"""Regression tests for the engines-pinned check's value logic (ENG-1006).

Background: lunar_policy's ``assert_true`` is a strict identity check
(``lambda v: v is True``), so a truthy *string* does not satisfy it. The check
used ``assert_true(value and str(value).strip())`` whose value is the string
itself (e.g. ``">=18"``), so every project that *correctly* pinned
``engines.node`` false-failed — the check could effectively only "pass" via the
missing-data path by failing for a different reason. The fix coerces the
expression to a real bool.

These tests pin that contract from both directions: a valid version string
PASSES, and empty / whitespace / missing / null values FAIL. The
project-detection gating (skip on non-Node components) is covered separately in
test_project_gating.py.
"""

import os
import sys
import unittest

# The check modules live in ../checks (no package __init__), import them flatly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "checks"))

from lunar_policy import Node, CheckStatus  # noqa: E402

from engines_pinned import check_engines_pinned  # noqa: E402

# Sentinel so a test can request "omit the engines_node key entirely" as
# distinct from "set it to None" (the collector emits null, not "", when
# engines.node is absent).
_OMIT = object()


def _node(engines_node=_OMIT):
    """A genuine Node project (project_exists=True), optionally pinning engines.

    workflows_finished=True models a completed collection: a missing path is
    *definitively* absent rather than "data may still be arriving" — the same
    modelling test_project_gating.py relies on.
    """
    nodejs = {
        "project_exists": True,
        "package_json_exists": True,
        "source": {"tool": "node", "integration": "code"},
    }
    if engines_node is not _OMIT:
        nodejs["engines_node"] = engines_node
    return Node.from_component_json(
        {"lang": {"nodejs": nodejs}},
        bundle_info={"workflows_finished": True},
    )


class TestEnginesPinnedPassesOnValidVersion(unittest.TestCase):
    """A pinned engines.node string must PASS (the ENG-1006 regression)."""

    def test_range_constraint_passes(self):
        # ">=18" is a truthy string, not True. Before the fix, assert_true's
        # ``v is True`` rejected it and this check false-failed.
        c = check_engines_pinned(node=_node(">=18"))
        self.assertEqual(c.status, CheckStatus.PASS)

    def test_exact_version_passes(self):
        c = check_engines_pinned(node=_node("18.17.0"))
        self.assertEqual(c.status, CheckStatus.PASS)

    def test_caret_range_passes(self):
        c = check_engines_pinned(node=_node("^18.0.0"))
        self.assertEqual(c.status, CheckStatus.PASS)


class TestEnginesPinnedFailsWhenUnpinned(unittest.TestCase):
    """Empty / whitespace / missing / null engines.node must FAIL."""

    def test_empty_string_fails(self):
        c = check_engines_pinned(node=_node(""))
        self.assertEqual(c.status, CheckStatus.FAIL)

    def test_whitespace_only_fails(self):
        c = check_engines_pinned(node=_node("   "))
        self.assertEqual(c.status, CheckStatus.FAIL)

    def test_missing_field_fails(self):
        # No engines_node key at all -> the explicit "not set" failure path.
        c = check_engines_pinned(node=_node())
        self.assertEqual(c.status, CheckStatus.FAIL)

    def test_null_fails(self):
        # The collector emits null (not "") when engines.node is absent.
        c = check_engines_pinned(node=_node(None))
        self.assertEqual(c.status, CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
