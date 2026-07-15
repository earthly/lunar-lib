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
check_disallowed_annotations = load_policy("disallowed-annotations")
check_disallowed_tag_patterns = load_policy("disallowed-tag-patterns")
check_domain_exists = load_policy("domain-exists")
check_system_exists = load_policy("system-exists")


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


class TestDisallowedAnnotations(unittest.TestCase):
    def test_unconfigured_skips(self):
        data = backstage_data(annotations={"backstage.io/skip-checks": "true"})
        self.assertTrue(is_skipped(check_disallowed_annotations(Node.from_component_json(data))))

    def test_forbidden_key_present_fails_and_names_it(self):
        with policy_vars(disallowed_annotations="backstage.io/skip-checks,internal.only"):
            data = backstage_data(annotations={"backstage.io/skip-checks": "true", "team": "x"})
            check = check_disallowed_annotations(Node.from_component_json(data))
            self.assertEqual(check.status, CheckStatus.FAIL)
            self.assertIn("backstage.io/skip-checks", check.failure_reasons[0])
            self.assertNotIn("internal.only", check.failure_reasons[0])

    def test_no_forbidden_key_passes(self):
        with policy_vars(disallowed_annotations="backstage.io/skip-checks"):
            data = backstage_data(annotations={"backstage.io/source-location": "url:x"})
            self.assertEqual(
                check_disallowed_annotations(Node.from_component_json(data)).status,
                CheckStatus.PASS,
            )

    def test_no_catalog_file_passes(self):
        # Pure deny-check: nothing present means nothing forbidden, even post-run.
        with policy_vars(disallowed_annotations="backstage.io/skip-checks"):
            self.assertEqual(
                check_disallowed_annotations(finished_node({})).status,
                CheckStatus.PASS,
            )

    def test_empty_value_still_counts_as_present(self):
        with policy_vars(disallowed_annotations="backstage.io/skip-checks"):
            data = backstage_data(annotations={"backstage.io/skip-checks": ""})
            self.assertEqual(
                check_disallowed_annotations(Node.from_component_json(data)).status,
                CheckStatus.FAIL,
            )


class TestDisallowedTagPatterns(unittest.TestCase):
    def test_unconfigured_skips(self):
        data = backstage_data(tags=["deprecated/legacy"])
        self.assertTrue(is_skipped(check_disallowed_tag_patterns(Node.from_component_json(data))))

    def test_matching_tag_fails_and_names_pattern_and_tag(self):
        with policy_vars(disallowed_tag_patterns="deprecated/*,internal-only"):
            data = backstage_data(tags=["deprecated/legacy", "tier1"])
            check = check_disallowed_tag_patterns(Node.from_component_json(data))
            self.assertEqual(check.status, CheckStatus.FAIL)
            self.assertIn("deprecated/*", check.failure_reasons[0])
            self.assertIn("deprecated/legacy", check.failure_reasons[0])

    def test_no_matching_tag_passes(self):
        with policy_vars(disallowed_tag_patterns="deprecated/*"):
            data = backstage_data(tags=["location/us-east-1", "tier1"])
            self.assertEqual(
                check_disallowed_tag_patterns(Node.from_component_json(data)).status,
                CheckStatus.PASS,
            )

    def test_no_catalog_file_passes(self):
        with policy_vars(disallowed_tag_patterns="deprecated/*"):
            self.assertEqual(
                check_disallowed_tag_patterns(finished_node({})).status,
                CheckStatus.PASS,
            )

    def test_matching_is_case_insensitive(self):
        with policy_vars(disallowed_tag_patterns="Deprecated/*"):
            data = backstage_data(tags=["deprecated/legacy"])
            self.assertEqual(
                check_disallowed_tag_patterns(Node.from_component_json(data)).status,
                CheckStatus.FAIL,
            )


def refs_node(refs=None):
    """Finished node with an optional .catalog.native.backstage.refs block.

    Referential-integrity checks read a data-less path when the collector isn't
    configured; the SDK only resolves that to a definite skip once workflows
    finish (mid-run it is PENDING), so these tests use a finished node.
    """
    backstage = {"valid": True}
    if refs is not None:
        backstage["refs"] = refs
    data = {"catalog": {"native": {"backstage": backstage}}}
    return Node.from_component_json(data, {"workflows_finished": True})


class TestDomainExists(unittest.TestCase):
    def test_unconfigured_skips(self):
        # Collector parsed catalog-info but backstage_url is not set: no .refs.
        self.assertTrue(is_skipped(check_domain_exists(refs_node(None))))

    def test_no_catalog_file_skips(self):
        # No catalog-info.yaml at all — nothing to cross-check, so skip (not
        # fail; the *-set checks own "should the field be set").
        self.assertTrue(is_skipped(check_domain_exists(finished_node({}))))

    def test_no_domain_declared_passes(self):
        # Configured, but this component declares no spec.domain.
        self.assertEqual(
            check_domain_exists(refs_node({"checked": True})).status,
            CheckStatus.PASS,
        )

    def test_exists_passes(self):
        self.assertEqual(
            check_domain_exists(
                refs_node({"checked": True, "domain": {"name": "payments", "exists": True}})
            ).status,
            CheckStatus.PASS,
        )

    def test_missing_domain_fails_and_names_it(self):
        check = check_domain_exists(
            refs_node({"checked": True, "domain": {"name": "typo-domain", "exists": False}})
        )
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("typo-domain", check.failure_reasons[0])

    def test_transient_error_skips(self):
        # An outage records {name, error}; the check must skip, not false-fail.
        self.assertTrue(
            is_skipped(
                check_domain_exists(
                    refs_node({"checked": True, "domain": {"name": "payments", "error": "HTTP 502"}})
                )
            )
        )


class TestSystemExists(unittest.TestCase):
    def test_unconfigured_skips(self):
        self.assertTrue(is_skipped(check_system_exists(refs_node(None))))

    def test_no_catalog_file_skips(self):
        self.assertTrue(is_skipped(check_system_exists(finished_node({}))))

    def test_no_system_declared_passes(self):
        self.assertEqual(
            check_system_exists(refs_node({"checked": True})).status,
            CheckStatus.PASS,
        )

    def test_exists_passes(self):
        self.assertEqual(
            check_system_exists(
                refs_node({"checked": True, "system": {"name": "payment-platform", "exists": True}})
            ).status,
            CheckStatus.PASS,
        )

    def test_missing_system_fails_and_names_it(self):
        check = check_system_exists(
            refs_node({"checked": True, "system": {"name": "typo-platform", "exists": False}})
        )
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("typo-platform", check.failure_reasons[0])

    def test_transient_error_skips(self):
        self.assertTrue(
            is_skipped(
                check_system_exists(
                    refs_node({"checked": True, "system": {"name": "payment-platform", "error": "timeout"}})
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
