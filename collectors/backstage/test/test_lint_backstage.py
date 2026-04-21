#!/usr/bin/env python3
"""Tests for lint_backstage.py."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lint_backstage import lint


def errors_with_severity(result, severity):
    return [e for e in result["errors"] if e["severity"] == severity]


class TestValidComponent(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Component",
                "metadata": {
                    "name": "payment-api",
                    "description": "Payment processing API",
                    "tags": ["payments", "api"],
                    "annotations": {
                        "backstage.io/techdocs-ref": "dir:.",
                        "pagerduty.com/integration-key": "PXXXXXX",
                    },
                },
                "spec": {
                    "type": "service",
                    "owner": "team-payments",
                    "lifecycle": "production",
                    "system": "payment-platform",
                },
            },
            "catalog-info.yaml",
        )

    def test_valid_and_no_errors(self):
        self.assertTrue(self.result["valid"])
        self.assertEqual(self.result["errors"], [])

    def test_raw_fields_preserved(self):
        self.assertEqual(self.result["apiVersion"], "backstage.io/v1alpha1")
        self.assertEqual(self.result["kind"], "Component")
        self.assertEqual(self.result["metadata"]["name"], "payment-api")
        self.assertEqual(self.result["spec"]["owner"], "team-payments")

    def test_annotations_keep_prefixes(self):
        annotations = self.result["metadata"]["annotations"]
        self.assertIn("backstage.io/techdocs-ref", annotations)
        self.assertIn("pagerduty.com/integration-key", annotations)

    def test_path_preserved(self):
        self.assertEqual(self.result["path"], "catalog-info.yaml")

    def test_exists_true(self):
        self.assertTrue(self.result["exists"])


class TestMinimalValid(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Component",
                "metadata": {"name": "minimal"},
                "spec": {},
            },
            "catalog-info.yaml",
        )

    def test_valid(self):
        self.assertTrue(self.result["valid"])
        self.assertEqual(errors_with_severity(self.result, "error"), [])


class TestMissingApiVersion(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {"kind": "Component", "metadata": {"name": "foo"}, "spec": {}},
            "catalog-info.yaml",
        )

    def test_invalid(self):
        self.assertFalse(self.result["valid"])

    def test_error_mentions_apiversion(self):
        messages = [e["message"] for e in self.result["errors"]]
        self.assertTrue(any("apiVersion" in m for m in messages))


class TestMissingKind(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "metadata": {"name": "foo"},
                "spec": {},
            },
            "catalog-info.yaml",
        )

    def test_invalid(self):
        self.assertFalse(self.result["valid"])

    def test_error_mentions_kind(self):
        messages = [e["message"] for e in self.result["errors"]]
        self.assertTrue(any("kind" in m for m in messages))


class TestMissingMetadata(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {"apiVersion": "backstage.io/v1alpha1", "kind": "Component", "spec": {}},
            "catalog-info.yaml",
        )

    def test_invalid(self):
        self.assertFalse(self.result["valid"])


class TestMissingMetadataName(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Component",
                "metadata": {"description": "no name here"},
                "spec": {},
            },
            "catalog-info.yaml",
        )

    def test_invalid(self):
        self.assertFalse(self.result["valid"])

    def test_error_mentions_metadata_name(self):
        messages = [e["message"] for e in self.result["errors"]]
        self.assertTrue(any("metadata.name" in m for m in messages))


class TestInvalidDNSName(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Component",
                "metadata": {"name": "Invalid Name!"},
                "spec": {},
            },
            "catalog-info.yaml",
        )

    def test_still_valid_overall(self):
        self.assertTrue(self.result["valid"])

    def test_warning_emitted(self):
        warnings = errors_with_severity(self.result, "warning")
        self.assertTrue(any("DNS-compatible" in w["message"] for w in warnings))


class TestUnknownKind(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "SomethingMadeUp",
                "metadata": {"name": "foo"},
                "spec": {},
            },
            "catalog-info.yaml",
        )

    def test_valid_with_warning(self):
        self.assertTrue(self.result["valid"])
        warnings = errors_with_severity(self.result, "warning")
        self.assertTrue(any("Unknown kind" in w["message"] for w in warnings))


class TestNonBackstageApiVersion(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {
                "apiVersion": "custom/v1",
                "kind": "Component",
                "metadata": {"name": "foo"},
                "spec": {},
            },
            "catalog-info.yaml",
        )

    def test_valid_with_warning(self):
        self.assertTrue(self.result["valid"])
        warnings = errors_with_severity(self.result, "warning")
        self.assertTrue(any("backstage.io/" in w["message"] for w in warnings))


class TestLocationKindWithoutSpec(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Location",
                "metadata": {"name": "infra-locations"},
            },
            "catalog-info.yaml",
        )

    def test_valid_no_warning_for_missing_spec(self):
        self.assertTrue(self.result["valid"])
        warnings = errors_with_severity(self.result, "warning")
        self.assertFalse(any("'spec' section" in w["message"] for w in warnings))


class TestComponentWithoutSpec(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Component",
                "metadata": {"name": "no-spec"},
            },
            "catalog-info.yaml",
        )

    def test_valid_with_warning(self):
        self.assertTrue(self.result["valid"])
        warnings = errors_with_severity(self.result, "warning")
        self.assertTrue(any("'spec' section" in w["message"] for w in warnings))


class TestTopLevelNotMapping(unittest.TestCase):
    def setUp(self):
        self.result = lint(["just", "a", "list"], "catalog-info.yaml")

    def test_invalid(self):
        self.assertFalse(self.result["valid"])

    def test_no_schema_fields_emitted(self):
        self.assertNotIn("apiVersion", self.result)
        self.assertNotIn("metadata", self.result)


class TestSpecNotMapping(unittest.TestCase):
    def setUp(self):
        self.result = lint(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Component",
                "metadata": {"name": "foo"},
                "spec": "not-a-mapping",
            },
            "catalog-info.yaml",
        )

    def test_invalid(self):
        self.assertFalse(self.result["valid"])

    def test_spec_not_passed_through(self):
        self.assertNotIn("spec", self.result)


class TestAnnotationsNotStripped(unittest.TestCase):
    """Collector must keep raw backstage.io/ and vendor prefixes verbatim."""

    def setUp(self):
        self.result = lint(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Component",
                "metadata": {
                    "name": "with-annotations",
                    "annotations": {
                        "backstage.io/source-location": "url:https://github.com/acme/repo",
                        "pagerduty.com/integration-key": "PXXXXX",
                        "grafana/dashboard-selector": "https://grafana.example.com/d/abc",
                        "custom-vendor.io/foo": "bar",
                    },
                },
                "spec": {"owner": "team-a", "lifecycle": "production"},
            },
            "catalog-info.yaml",
        )

    def test_all_prefixes_preserved(self):
        annotations = self.result["metadata"]["annotations"]
        self.assertIn("backstage.io/source-location", annotations)
        self.assertIn("pagerduty.com/integration-key", annotations)
        self.assertIn("grafana/dashboard-selector", annotations)
        self.assertIn("custom-vendor.io/foo", annotations)


class TestMetadataNameEdgeCases(unittest.TestCase):
    def _make_component(self, name):
        return {
            "apiVersion": "backstage.io/v1alpha1",
            "kind": "Component",
            "metadata": {"name": name},
            "spec": {},
        }

    def test_simple_valid(self):
        result = lint(self._make_component("my-service"), "catalog-info.yaml")
        warnings = errors_with_severity(result, "warning")
        self.assertFalse(any("DNS-compatible" in w["message"] for w in warnings))

    def test_with_dots(self):
        result = lint(self._make_component("my.service"), "catalog-info.yaml")
        warnings = errors_with_severity(result, "warning")
        self.assertFalse(any("DNS-compatible" in w["message"] for w in warnings))

    def test_with_underscores(self):
        result = lint(self._make_component("my_service"), "catalog-info.yaml")
        warnings = errors_with_severity(result, "warning")
        self.assertFalse(any("DNS-compatible" in w["message"] for w in warnings))

    def test_uppercase_warns(self):
        result = lint(self._make_component("MyService"), "catalog-info.yaml")
        warnings = errors_with_severity(result, "warning")
        self.assertTrue(any("DNS-compatible" in w["message"] for w in warnings))


if __name__ == "__main__":
    unittest.main()
