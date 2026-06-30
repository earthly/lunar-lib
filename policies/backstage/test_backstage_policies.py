"""Unit tests for the configurable backstage policies (required annotations + tag patterns)."""

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


check_required_annotations = load_policy("required-annotations")
check_required_tag_patterns = load_policy("required-tag-patterns")


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


def backstage_data(annotations=None, tags=None):
    """Build a Component JSON with a present .catalog.native.backstage namespace."""
    metadata = {}
    if annotations is not None:
        metadata["annotations"] = annotations
    if tags is not None:
        metadata["tags"] = tags
    return {"catalog": {"native": {"backstage": {"metadata": metadata}}}}


def finished_node(data):
    """Node with workflows marked finished.

    The SDK treats genuinely-absent data as no-data (PENDING) *during* a run and
    only as a hard failure once workflows finish — same semantics every check in
    this policy relies on. Use this when asserting the missing-catalog-file path.
    """
    return Node.from_component_json(data, {"workflows_finished": True})


class TestRequiredAnnotations(unittest.TestCase):
    def test_unconfigured_skips(self):
        data = backstage_data(annotations={"backstage.io/source-location": "url:x"})
        self.assertTrue(is_skipped(check_required_annotations(Node.from_component_json(data))))

    def test_no_catalog_file_fails_when_configured(self):
        with policy_vars(required_annotations="backstage.io/source-location"):
            check = check_required_annotations(finished_node({}))
            self.assertEqual(check.status, CheckStatus.FAIL)
            self.assertIn("No catalog-info.yaml", check.failure_reasons[0])

    def test_all_present_passes(self):
        with policy_vars(required_annotations="backstage.io/source-location,pagerduty.com/integration-key"):
            data = backstage_data(annotations={
                "backstage.io/source-location": "url:https://github.com/acme/x",
                "pagerduty.com/integration-key": "PXXXX",
            })
            self.assertEqual(
                check_required_annotations(Node.from_component_json(data)).status,
                CheckStatus.PASS,
            )

    def test_missing_annotation_fails_and_names_it(self):
        with policy_vars(required_annotations="backstage.io/source-location,pagerduty.com/integration-key"):
            data = backstage_data(annotations={"backstage.io/source-location": "url:x"})
            check = check_required_annotations(Node.from_component_json(data))
            self.assertEqual(check.status, CheckStatus.FAIL)
            self.assertIn("pagerduty.com/integration-key", check.failure_reasons[0])

    def test_empty_value_counts_as_missing(self):
        with policy_vars(required_annotations="backstage.io/source-location"):
            data = backstage_data(annotations={"backstage.io/source-location": "  "})
            self.assertEqual(
                check_required_annotations(Node.from_component_json(data)).status,
                CheckStatus.FAIL,
            )

    def test_no_annotations_block_fails(self):
        with policy_vars(required_annotations="backstage.io/source-location"):
            data = backstage_data()  # file present, no metadata.annotations
            self.assertEqual(
                check_required_annotations(Node.from_component_json(data)).status,
                CheckStatus.FAIL,
            )


class TestRequiredTagPatterns(unittest.TestCase):
    def test_unconfigured_skips(self):
        data = backstage_data(tags=["location/us-east-1"])
        self.assertTrue(is_skipped(check_required_tag_patterns(Node.from_component_json(data))))

    def test_no_catalog_file_fails_when_configured(self):
        with policy_vars(required_tag_patterns="location/*"):
            check = check_required_tag_patterns(finished_node({}))
            self.assertEqual(check.status, CheckStatus.FAIL)
            self.assertIn("No catalog-info.yaml", check.failure_reasons[0])

    def test_each_pattern_matched_passes(self):
        with policy_vars(required_tag_patterns="location/*,runs-on/*"):
            data = backstage_data(tags=["location/us-east-1", "runs-on/self-hosted", "tier1"])
            self.assertEqual(
                check_required_tag_patterns(Node.from_component_json(data)).status,
                CheckStatus.PASS,
            )

    def test_unmatched_pattern_fails_and_names_it(self):
        with policy_vars(required_tag_patterns="location/*,runs-on/*"):
            data = backstage_data(tags=["location/us-east-1"])
            check = check_required_tag_patterns(Node.from_component_json(data))
            self.assertEqual(check.status, CheckStatus.FAIL)
            self.assertIn("runs-on/*", check.failure_reasons[0])

    def test_glob_matches_prefix(self):
        with policy_vars(required_tag_patterns="location/*"):
            data = backstage_data(tags=["location/eu-west-2"])
            self.assertEqual(
                check_required_tag_patterns(Node.from_component_json(data)).status,
                CheckStatus.PASS,
            )

    def test_matching_is_case_insensitive(self):
        with policy_vars(required_tag_patterns="Location/*"):
            data = backstage_data(tags=["location/us-east-1"])
            self.assertEqual(
                check_required_tag_patterns(Node.from_component_json(data)).status,
                CheckStatus.PASS,
            )

    def test_no_tags_block_fails(self):
        with policy_vars(required_tag_patterns="location/*"):
            data = backstage_data()  # file present, no metadata.tags
            self.assertEqual(
                check_required_tag_patterns(Node.from_component_json(data)).status,
                CheckStatus.FAIL,
            )


if __name__ == "__main__":
    unittest.main()
