#!/usr/bin/env python3
"""Tests for lint_backstage.py."""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
from lint_backstage import lint, lint_documents

SCRIPT = os.path.join(HERE, "..", "lint_backstage.py")


def errors_with_severity(result, severity):
    return [e for e in result["errors"] if e["severity"] == severity]


def _component(name, **spec):
    return {
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "Component",
        "metadata": {"name": name},
        "spec": spec,
    }


def _entity(kind, name, **spec):
    return {
        "apiVersion": "backstage.io/v1alpha1",
        "kind": kind,
        "metadata": {"name": name},
        "spec": spec,
    }


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

    def test_no_exists_field(self):
        # Object presence IS the signal; no redundant `exists: true` field.
        self.assertNotIn("exists", self.result)


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


def _component_with_tags(tags):
    return {
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "Component",
        "metadata": {"name": "svc", "tags": tags},
        "spec": {},
    }


class TestValidTags(unittest.TestCase):
    def _lint(self, tags):
        return lint(_component_with_tags(tags), "catalog-info.yaml")

    def test_simple_tags_valid(self):
        result = self._lint(["payments", "api", "go"])
        self.assertTrue(result["valid"])
        self.assertEqual(errors_with_severity(result, "error"), [])

    def test_plus_and_hash_allowed(self):
        # Backstage's isValidTag permits '+' and '#' (common for language tags).
        result = self._lint(["c++", "c#", "f#"])
        self.assertTrue(result["valid"])
        self.assertEqual(errors_with_severity(result, "error"), [])

    def test_digits_and_dashes_valid(self):
        result = self._lint(["v1", "us-east-1", "team-payments-2"])
        self.assertTrue(result["valid"])
        self.assertEqual(errors_with_severity(result, "error"), [])

    def test_max_length_63_valid(self):
        result = self._lint(["a" * 63])
        self.assertTrue(result["valid"])
        self.assertEqual(errors_with_severity(result, "error"), [])

    def test_no_tags_field_valid(self):
        result = lint(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Component",
                "metadata": {"name": "svc"},
                "spec": {},
            },
            "catalog-info.yaml",
        )
        self.assertTrue(result["valid"])
        self.assertEqual(errors_with_severity(result, "error"), [])

    def test_empty_tag_list_valid(self):
        result = self._lint([])
        self.assertTrue(result["valid"])
        self.assertEqual(errors_with_severity(result, "error"), [])


class TestSlashTagRejected(unittest.TestCase):
    """The reported FR: catalog-info.yaml permits a slash but Backstage rejects it."""

    def setUp(self):
        self.result = lint(
            _component_with_tags(["hosting/internal"]), "catalog-info.yaml"
        )

    def test_invalid(self):
        self.assertFalse(self.result["valid"])

    def test_error_names_the_offending_tag(self):
        messages = [e["message"] for e in self.result["errors"]]
        self.assertTrue(any("hosting/internal" in m for m in messages))

    def test_error_severity_is_error(self):
        self.assertTrue(
            any(
                e["severity"] == "error" and "tags" in e["message"]
                for e in self.result["errors"]
            )
        )


class TestInvalidTagShapes(unittest.TestCase):
    def _lint(self, tags):
        result = lint(_component_with_tags(tags), "catalog-info.yaml")
        return result, errors_with_severity(result, "error")

    def test_uppercase_rejected(self):
        result, errs = self._lint(["Backend"])
        self.assertFalse(result["valid"])
        self.assertTrue(errs)

    def test_space_rejected(self):
        result, errs = self._lint(["my tag"])
        self.assertFalse(result["valid"])
        self.assertTrue(errs)

    def test_dot_rejected(self):
        result, errs = self._lint(["my.tag"])
        self.assertFalse(result["valid"])
        self.assertTrue(errs)

    def test_leading_dash_rejected(self):
        result, _ = self._lint(["-foo"])
        self.assertFalse(result["valid"])

    def test_trailing_dash_rejected(self):
        result, _ = self._lint(["foo-"])
        self.assertFalse(result["valid"])

    def test_double_dash_rejected(self):
        result, _ = self._lint(["a--b"])
        self.assertFalse(result["valid"])

    def test_over_63_chars_rejected(self):
        result, errs = self._lint(["a" * 64])
        self.assertFalse(result["valid"])
        self.assertTrue(any("63" in e["message"] for e in errs))

    def test_empty_string_tag_rejected(self):
        result, _ = self._lint([""])
        self.assertFalse(result["valid"])

    def test_non_string_tag_rejected(self):
        result, _ = self._lint([123])
        self.assertFalse(result["valid"])

    def test_tags_not_a_list_rejected(self):
        # A bare string (not a list) — Backstage requires an array.
        result, errs = self._lint("payments")
        self.assertFalse(result["valid"])
        self.assertTrue(any("list" in e["message"] for e in errs))

    def test_multiple_invalid_tags_each_reported(self):
        result, errs = self._lint(["valid-tag", "bad/tag", "AlsoBad"])
        self.assertFalse(result["valid"])
        joined = " ".join(e["message"] for e in errs)
        self.assertIn("bad/tag", joined)
        self.assertIn("AlsoBad", joined)


class TestMultiDocValid(unittest.TestCase):
    """A legal multi-entity file (Component + API) — the reported bug."""

    def setUp(self):
        self.result = lint_documents(
            [
                _component(
                    "payment-api",
                    owner="team-payments",
                    lifecycle="production",
                    system="payment-platform",
                ),
                _entity("API", "payment-api-grpc", owner="team-payments"),
            ],
            "catalog-info.yaml",
        )

    def test_valid_overall(self):
        self.assertTrue(self.result["valid"])
        self.assertEqual(self.result["errors"], [])

    def test_all_entities_listed(self):
        kinds = [e["kind"] for e in self.result["entities"]]
        names = [e["metadata"]["name"] for e in self.result["entities"]]
        self.assertEqual(kinds, ["Component", "API"])
        self.assertEqual(names, ["payment-api", "payment-api-grpc"])

    def test_primary_is_the_component(self):
        # owner/lifecycle/system are hoisted from the Component so the
        # owner-set / lifecycle-set / system-set policies keep working.
        self.assertEqual(self.result["kind"], "Component")
        self.assertEqual(self.result["metadata"]["name"], "payment-api")
        self.assertEqual(self.result["spec"]["owner"], "team-payments")
        self.assertEqual(self.result["spec"]["system"], "payment-platform")

    def test_path_preserved(self):
        self.assertEqual(self.result["path"], "catalog-info.yaml")


class TestMultiDocPrimarySelection(unittest.TestCase):
    def test_first_component_wins_even_when_not_first_doc(self):
        result = lint_documents(
            [
                _entity("API", "the-api", owner="api-team"),
                _component("the-comp", owner="comp-team", lifecycle="production"),
            ],
            "catalog-info.yaml",
        )
        self.assertEqual(result["kind"], "Component")
        self.assertEqual(result["metadata"]["name"], "the-comp")
        self.assertEqual(result["spec"]["owner"], "comp-team")

    def test_falls_back_to_first_entity_when_no_component(self):
        result = lint_documents(
            [
                _entity("System", "my-system", owner="platform", domain="my-domain"),
                _entity("Domain", "my-domain", owner="platform"),
            ],
            "catalog-info.yaml",
        )
        self.assertEqual(result["kind"], "System")
        self.assertEqual(result["metadata"]["name"], "my-system")


class TestMultiDocInvalidEntity(unittest.TestCase):
    """One bad entity fails the whole file, with a locator on the message."""

    def setUp(self):
        bad = _entity("API", "bad-api", owner="t")
        bad["metadata"]["tags"] = ["hosting/internal"]  # slash → Backstage rejects
        self.result = lint_documents(
            [_component("good-comp", owner="t", lifecycle="production"), bad],
            "catalog-info.yaml",
        )

    def test_invalid_overall(self):
        self.assertFalse(self.result["valid"])

    def test_error_locates_the_offending_document(self):
        messages = [e["message"] for e in self.result["errors"]]
        self.assertTrue(any("document 2 (API 'bad-api')" in m for m in messages))
        self.assertTrue(any("hosting/internal" in m for m in messages))

    def test_error_carries_entity_index(self):
        tag_errors = [e for e in self.result["errors"] if "hosting/internal" in e["message"]]
        self.assertTrue(tag_errors)
        self.assertEqual(tag_errors[0]["entity"], 1)

    def test_good_entity_still_recorded_valid(self):
        self.assertTrue(self.result["entities"][0]["valid"])
        self.assertFalse(self.result["entities"][1]["valid"])


class TestSingleDocBackwardCompat(unittest.TestCase):
    """A one-element list keeps the pre-multi-doc top-level shape unchanged."""

    def setUp(self):
        self.doc = _component(
            "solo", owner="solo-team", lifecycle="production", system="solo-sys"
        )
        self.result = lint_documents([self.doc], "catalog-info.yaml")

    def test_top_level_matches_single_lint(self):
        single = lint(self.doc, "catalog-info.yaml")
        for key in ("valid", "errors", "path", "apiVersion", "kind", "metadata", "spec"):
            self.assertEqual(self.result[key], single[key])

    def test_errors_not_prefixed_for_single_entity(self):
        # A bad single-entity file keeps its message byte-identical (no locator).
        bad = _component("solo")
        bad["metadata"]["tags"] = ["Bad/Tag"]
        agg = lint_documents([bad], "catalog-info.yaml")
        single = lint(bad, "catalog-info.yaml")
        self.assertEqual(
            [e["message"] for e in agg["errors"]],
            [e["message"] for e in single["errors"]],
        )
        self.assertFalse(any("document" in e["message"] for e in agg["errors"]))

    def test_entities_has_one(self):
        self.assertEqual(len(self.result["entities"]), 1)


class TestEmptyDocumentsFiltered(unittest.TestCase):
    def test_null_docs_dropped(self):
        # A trailing `---` (null doc) is not an entity.
        result = lint_documents(
            [_component("a", owner="t", lifecycle="production"), None],
            "catalog-info.yaml",
        )
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["entities"]), 1)

    def test_all_null_is_no_entities(self):
        result = lint_documents([None], "catalog-info.yaml")
        self.assertFalse(result["valid"])
        self.assertTrue(any("no entities" in e["message"] for e in result["errors"]))
        self.assertNotIn("entities", result)


class TestMainStdinContract(unittest.TestCase):
    """main() over stdin — the exact contract main.sh drives (`yq ea '[.]'`)."""

    def _run(self, payload):
        proc = subprocess.run(
            [sys.executable, SCRIPT, "--path", "catalog-info.yaml"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)

    def test_json_array_of_entities(self):
        out = self._run(
            [
                _component("c", owner="t", lifecycle="production", system="s"),
                _entity("API", "a", owner="t"),
            ]
        )
        self.assertTrue(out["valid"])
        self.assertEqual(out["kind"], "Component")
        self.assertEqual(len(out["entities"]), 2)

    def test_bare_object_still_accepted(self):
        out = self._run(_component("c", owner="t"))
        self.assertTrue(out["valid"])
        self.assertEqual(len(out["entities"]), 1)

    def test_invalid_json_reports_parser_error(self):
        proc = subprocess.run(
            [sys.executable, SCRIPT, "--path", "catalog-info.yaml"],
            input="{not: valid json",
            capture_output=True,
            text=True,
            check=True,
        )
        out = json.loads(proc.stdout)
        self.assertFalse(out["valid"])
        self.assertTrue(any("Invalid parser output" in e["message"] for e in out["errors"]))


if __name__ == "__main__":
    unittest.main()
