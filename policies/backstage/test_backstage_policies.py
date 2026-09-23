"""Unit tests for the backstage policy checks."""

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


check_catalog_info_exists = load_policy("catalog-info-exists")
check_catalog_info_valid = load_policy("catalog-info-valid")
check_owner_set = load_policy("owner-set")
check_lifecycle_set = load_policy("lifecycle-set")
check_system_set = load_policy("system-set")
check_required_annotations = load_policy("required-annotations")
check_required_tag_patterns = load_policy("required-tag-patterns")
check_disallowed_annotations = load_policy("disallowed-annotations")
check_disallowed_tag_patterns = load_policy("disallowed-tag-patterns")
check_domain_exists = load_policy("domain-exists")
check_system_exists = load_policy("system-exists")
check_system_domain_exists = load_policy("system-domain-exists")

from constraints import (
    parse_required_annotations,
    validate_value,
    ConstraintConfigError,
)


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


def skip_reason(check):
    """The reason text of a skip, so tests can tell *which* gate skipped."""
    return next(
        (r.failure_message for r in check._results if r.result == CheckStatus.SKIPPED),
        None,
    )


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


class TestSystemDomainExists(unittest.TestCase):
    """Transitive RI: component -> its system -> that system's domain."""

    def test_unconfigured_skips(self):
        # Collector parsed catalog-info but backstage_url is not set: no .refs.
        self.assertTrue(is_skipped(check_system_domain_exists(refs_node(None))))

    def test_no_catalog_file_skips(self):
        self.assertTrue(is_skipped(check_system_domain_exists(finished_node({}))))

    def test_no_system_declared_passes(self):
        # Configured, but this component declares no spec.system, so the
        # collector never reached a system_domain.
        self.assertEqual(
            check_system_domain_exists(refs_node({"checked": True})).status,
            CheckStatus.PASS,
        )

    def test_system_missing_passes_here(self):
        # An unresolvable system is `system-exists`'s failure to report. This
        # check must not pile a second failure onto the same root cause.
        self.assertEqual(
            check_system_domain_exists(
                refs_node({"checked": True, "system": {"name": "nope", "exists": False}})
            ).status,
            CheckStatus.PASS,
        )

    def test_system_without_domain_passes(self):
        # A System that belongs to no domain is legitimate — not a violation.
        self.assertEqual(
            check_system_domain_exists(
                refs_node({"checked": True, "system": {"name": "standalone", "exists": True}})
            ).status,
            CheckStatus.PASS,
        )

    def test_exists_passes(self):
        self.assertEqual(
            check_system_domain_exists(
                refs_node({
                    "checked": True,
                    "system": {"name": "payment-platform", "exists": True},
                    "system_domain": {
                        "name": "payments",
                        "exists": True,
                        "via_system": "payment-platform",
                    },
                })
            ).status,
            CheckStatus.PASS,
        )

    def test_missing_domain_fails_and_names_domain_and_system(self):
        check = check_system_domain_exists(
            refs_node({
                "checked": True,
                "system": {"name": "orphan-system", "exists": True},
                "system_domain": {
                    "name": "ghost-domain",
                    "exists": False,
                    "via_system": "orphan-system",
                },
            })
        )
        self.assertEqual(check.status, CheckStatus.FAIL)
        reason = check.failure_reasons[0]
        # Both halves matter: the domain that is missing, and the system that
        # points at it — the latter is where the fix actually goes.
        self.assertIn("ghost-domain", reason)
        self.assertIn("orphan-system", reason)

    def test_transient_error_skips(self):
        self.assertTrue(
            is_skipped(
                check_system_domain_exists(
                    refs_node({
                        "checked": True,
                        "system": {"name": "payment-platform", "exists": True},
                        "system_domain": {
                            "name": "payments",
                            "error": "HTTP 502",
                            "via_system": "payment-platform",
                        },
                    })
                )
            )
        )

    def test_domain_exists_ignores_system_domain(self):
        # The two checks must stay independent: a dangling *transitive* domain
        # is not `domain-exists`'s business (this component declares no
        # spec.domain of its own).
        self.assertEqual(
            check_domain_exists(
                refs_node({
                    "checked": True,
                    "system_domain": {
                        "name": "ghost-domain",
                        "exists": False,
                        "via_system": "orphan-system",
                    },
                })
            ).status,
            CheckStatus.PASS,
        )


class TestConstraintParsing(unittest.TestCase):
    """Parsing the required_annotations input into normalized entries."""

    def test_empty_is_no_entries(self):
        self.assertEqual(parse_required_annotations(""), [])
        self.assertEqual(parse_required_annotations("   "), [])

    def test_legacy_comma_string_is_presence_only(self):
        entries = parse_required_annotations("a.io/one, b.io/two")
        self.assertEqual(entries, [
            {"key": "a.io/one", "constraints": {}},
            {"key": "b.io/two", "constraints": {}},
        ])

    def test_single_bare_key(self):
        self.assertEqual(
            parse_required_annotations("backstage.io/source-location"),
            [{"key": "backstage.io/source-location", "constraints": {}}],
        )

    def test_yaml_list_mixed_bare_and_typed(self):
        raw = (
            "- key: example.com/service-tier\n"
            "  type: integer\n"
            "  min: 0\n"
            "  max: 5\n"
            "- backstage.io/source-location\n"
        )
        entries = parse_required_annotations(raw)
        self.assertEqual(entries[0]["key"], "example.com/service-tier")
        self.assertEqual(entries[0]["constraints"],
                         {"type": "integer", "min": 0, "max": 5})
        self.assertEqual(entries[1], {"key": "backstage.io/source-location",
                                      "constraints": {}})

    def test_invalid_yaml_is_misconfig(self):
        with self.assertRaises(ConstraintConfigError):
            parse_required_annotations("- key: x\n bad: [unclosed\n")

    def test_top_level_mapping_is_misconfig(self):
        with self.assertRaises(ConstraintConfigError):
            parse_required_annotations("key: just-a-mapping")

    def test_entry_without_key_is_misconfig(self):
        with self.assertRaises(ConstraintConfigError):
            parse_required_annotations("- type: integer\n  min: 0\n")

    def test_non_scalar_non_mapping_entry_is_misconfig(self):
        with self.assertRaises(ConstraintConfigError):
            parse_required_annotations("- [1, 2, 3]\n")


class TestConstraintSpecMisconfig(unittest.TestCase):
    """A broken constraint spec must raise (surfacing as an error), detected at
    parse time so it fires even when the annotation is absent."""

    def _bad(self, raw):
        with self.assertRaises(ConstraintConfigError):
            parse_required_annotations(raw)

    def test_unknown_type(self):
        self._bad("- key: k\n  type: date\n")

    def test_min_greater_than_max(self):
        self._bad("- key: k\n  type: integer\n  min: 10\n  max: 5\n")

    def test_min_length_greater_than_max_length(self):
        self._bad("- key: k\n  type: string\n  min_length: 10\n  max_length: 2\n")

    def test_invalid_regex(self):
        self._bad("- key: k\n  type: string\n  pattern: '([unclosed'\n")

    def test_numeric_bound_on_string(self):
        self._bad("- key: k\n  type: string\n  min: 3\n")

    def test_pattern_on_integer(self):
        self._bad("- key: k\n  type: integer\n  pattern: '\\d+'\n")

    def test_length_on_boolean(self):
        self._bad("- key: k\n  type: boolean\n  min_length: 1\n")

    def test_enum_item_wrong_type(self):
        self._bad("- key: k\n  type: integer\n  enum: [1, two, 3]\n")

    def test_empty_enum(self):
        self._bad("- key: k\n  enum: []\n")

    def test_non_numeric_min(self):
        self._bad("- key: k\n  type: integer\n  min: abc\n")


class TestValidateValue(unittest.TestCase):
    """validate_value on an already-parsed constraint spec (no YAML needed)."""

    def test_integer_in_range_passes(self):
        self.assertIsNone(validate_value("k", "3", {"type": "integer",
                                                    "min": 0, "max": 5}))

    def test_integer_above_max_fails(self):
        msg = validate_value("k", "7", {"type": "integer", "min": 0, "max": 5})
        self.assertIn("above maximum 5", msg)

    def test_integer_below_min_fails(self):
        msg = validate_value("k", "-1", {"type": "integer", "min": 0, "max": 5})
        self.assertIn("below minimum 0", msg)

    def test_non_integer_value_fails(self):
        msg = validate_value("k", "2.5", {"type": "integer"})
        self.assertIn("not a valid integer", msg)

    def test_number_accepts_decimal(self):
        self.assertIsNone(validate_value("k", "2.5", {"type": "number",
                                                      "max": 3}))

    def test_string_pattern_match_passes(self):
        self.assertIsNone(validate_value(
            "k", "user@example.com",
            {"type": "string", "pattern": r"^[^@]+@[^@]+\.[^@]+$"}))

    def test_string_pattern_mismatch_fails(self):
        msg = validate_value(
            "k", "nope",
            {"type": "string", "pattern": r"^[^@]+@[^@]+\.[^@]+$"})
        self.assertIn("does not match", msg)

    def test_pattern_is_full_match(self):
        # A partial match must fail: pattern must anchor the whole value.
        msg = validate_value("k", "abc123", {"type": "string",
                                             "pattern": r"[a-z]+"})
        self.assertIn("does not match", msg)

    def test_min_length_fails(self):
        msg = validate_value("k", "ab", {"type": "string", "min_length": 3})
        self.assertIn("shorter than", msg)

    def test_max_length_fails(self):
        msg = validate_value("k", "abcd", {"type": "string", "max_length": 3})
        self.assertIn("longer than", msg)

    def test_boolean_passes(self):
        self.assertIsNone(validate_value("k", "true", {"type": "boolean"}))

    def test_boolean_rejects_non_bool(self):
        self.assertIn("not a valid boolean",
                      validate_value("k", "yes", {"type": "boolean"}))


class TestEnumTypeInteraction(unittest.TestCase):
    """Fry's flagged gap: enum items are typed by YAML on parse, so enum
    comparison must happen in the declared type's domain. Exercised end-to-end
    through parse + validate."""

    def _spec(self, raw):
        return parse_required_annotations(raw)[0]["constraints"]

    def test_string_enum_of_yaml_ints_matches_string_value(self):
        # `type: string` (default) + `enum: [1, 2, 3]`: without coercion the
        # compare would be "2" == 2 (always false). Items must coerce to string.
        spec = self._spec("- key: k\n  enum: [1, 2, 3]\n")
        self.assertIsNone(validate_value("k", "2", spec))

    def test_integer_enum_matches_integer_value(self):
        spec = self._spec("- key: k\n  type: integer\n  enum: [1, 2, 3]\n")
        self.assertIsNone(validate_value("k", "2", spec))

    def test_value_outside_enum_fails(self):
        spec = self._spec("- key: k\n  type: integer\n  enum: [1, 2, 3]\n")
        self.assertIn("not one of", validate_value("k", "9", spec))

    def test_string_enum_of_words(self):
        spec = self._spec("- key: k\n  enum: [production, staging, development]\n")
        self.assertIsNone(validate_value("k", "staging", spec))
        self.assertIn("not one of", validate_value("k", "qa", spec))


class TestRequiredAnnotationsTyped(unittest.TestCase):
    """Integration: the check end-to-end with typed constraints."""

    def test_integer_range_passes(self):
        raw = "- key: example.com/service-tier\n  type: integer\n  min: 0\n  max: 5\n"
        with policy_vars(required_annotations=raw):
            data = backstage_data(annotations={"example.com/service-tier": "3"})
            self.assertEqual(
                check_required_annotations(Node.from_component_json(data)).status,
                CheckStatus.PASS,
            )

    def test_integer_out_of_range_fails_with_message(self):
        raw = "- key: example.com/service-tier\n  type: integer\n  min: 0\n  max: 5\n"
        with policy_vars(required_annotations=raw):
            data = backstage_data(annotations={"example.com/service-tier": "7"})
            check = check_required_annotations(Node.from_component_json(data))
            self.assertEqual(check.status, CheckStatus.FAIL)
            self.assertIn("above maximum 5", check.failure_reasons[0])

    def test_regex_constraint(self):
        raw = ("- key: example.com/contact\n  type: string\n"
               "  pattern: '^[^@]+@[^@]+\\.[^@]+$'\n")
        with policy_vars(required_annotations=raw):
            good = backstage_data(annotations={"example.com/contact": "a@b.com"})
            self.assertEqual(
                check_required_annotations(Node.from_component_json(good)).status,
                CheckStatus.PASS,
            )
            bad = backstage_data(annotations={"example.com/contact": "not-an-email"})
            self.assertEqual(
                check_required_annotations(Node.from_component_json(bad)).status,
                CheckStatus.FAIL,
            )

    def test_missing_typed_key_fails(self):
        raw = "- key: example.com/service-tier\n  type: integer\n  min: 0\n  max: 5\n"
        with policy_vars(required_annotations=raw):
            data = backstage_data(annotations={"other": "x"})
            check = check_required_annotations(Node.from_component_json(data))
            self.assertEqual(check.status, CheckStatus.FAIL)
            self.assertIn("example.com/service-tier", check.failure_reasons[0])

    def test_yaml_list_presence_only_still_works(self):
        raw = "- backstage.io/source-location\n- pagerduty.com/integration-key\n"
        with policy_vars(required_annotations=raw):
            data = backstage_data(annotations={
                "backstage.io/source-location": "url:x",
                "pagerduty.com/integration-key": "PXXXX",
            })
            self.assertEqual(
                check_required_annotations(Node.from_component_json(data)).status,
                CheckStatus.PASS,
            )

    def test_misconfig_surfaces_as_error(self):
        # min > max is a broken spec: the check must not silently pass.
        raw = "- key: k\n  type: integer\n  min: 10\n  max: 0\n"
        with policy_vars(required_annotations=raw):
            data = backstage_data(annotations={"k": "5"})
            with self.assertRaises(ConstraintConfigError):
                check_required_annotations(Node.from_component_json(data))


# Every check in the policy, paired with the inputs it needs to get past its own
# opt-in gate and reach the catalog-presence gate. Without those inputs the four
# configurable checks skip on "nothing configured" and the assertions below would
# pass vacuously.
ALL_CHECKS = [
    ("catalog-info-exists", check_catalog_info_exists, {}),
    ("catalog-info-valid", check_catalog_info_valid, {}),
    ("owner-set", check_owner_set, {}),
    ("lifecycle-set", check_lifecycle_set, {}),
    ("system-set", check_system_set, {}),
    ("domain-exists", check_domain_exists, {}),
    ("system-exists", check_system_exists, {}),
    ("system-domain-exists", check_system_domain_exists, {}),
    (
        "required-annotations",
        check_required_annotations,
        {"required_annotations": "backstage.io/source-location"},
    ),
    (
        "required-tag-patterns",
        check_required_tag_patterns,
        {"required_tag_patterns": "location/*"},
    ),
    (
        "disallowed-annotations",
        check_disallowed_annotations,
        {"disallowed_annotations": "backstage.io/skip-checks"},
    ),
    (
        "disallowed-tag-patterns",
        check_disallowed_tag_patterns,
        {"disallowed_tag_patterns": "deprecated/*"},
    ),
]

# What each check resolves to on a missing catalog file with the mode OFF — the
# behaviour this input must leave untouched.
DEFAULT_NO_CATALOG = {
    "catalog-info-exists": CheckStatus.FAIL,
    "catalog-info-valid": CheckStatus.FAIL,
    "owner-set": CheckStatus.FAIL,
    "lifecycle-set": CheckStatus.FAIL,
    "system-set": CheckStatus.FAIL,
    "required-annotations": CheckStatus.FAIL,
    "required-tag-patterns": CheckStatus.FAIL,
    # Pure deny-checks: nothing present means nothing forbidden.
    "disallowed-annotations": CheckStatus.PASS,
    "disallowed-tag-patterns": CheckStatus.PASS,
    # Referential integrity already skips without .refs.checked.
    "domain-exists": CheckStatus.SKIPPED,
    "system-exists": CheckStatus.SKIPPED,
    "system-domain-exists": CheckStatus.SKIPPED,
}


class TestSkipWhenNoCatalogInfo(unittest.TestCase):
    """The `skip_when_no_catalog_info` input, across all twelve checks."""

    def test_every_check_skips_when_set(self):
        for name, check_fn, inputs in ALL_CHECKS:
            with self.subTest(check=name):
                with policy_vars(skip_when_no_catalog_info="true", **inputs):
                    check = check_fn(finished_node({}))
                    self.assertTrue(is_skipped(check))
                    # Assert on the reason, not just the status: the four
                    # configurable checks have a skip gate of their own.
                    self.assertIn("skip_when_no_catalog_info", skip_reason(check))

    def test_default_leaves_every_check_unchanged(self):
        for name, check_fn, inputs in ALL_CHECKS:
            with self.subTest(check=name):
                with policy_vars(**inputs):
                    check = check_fn(finished_node({}))
                    expected = DEFAULT_NO_CATALOG[name]
                    if expected == CheckStatus.SKIPPED:
                        self.assertTrue(is_skipped(check))
                        self.assertNotIn(
                            "skip_when_no_catalog_info", skip_reason(check)
                        )
                    else:
                        self.assertEqual(check.status, expected)

    def test_explicit_false_leaves_every_check_unchanged(self):
        for name, check_fn, inputs in ALL_CHECKS:
            with self.subTest(check=name):
                with policy_vars(skip_when_no_catalog_info="false", **inputs):
                    check = check_fn(finished_node({}))
                    expected = DEFAULT_NO_CATALOG[name]
                    if expected == CheckStatus.SKIPPED:
                        self.assertTrue(is_skipped(check))
                    else:
                        self.assertEqual(check.status, expected)

    def test_set_does_not_skip_a_component_that_has_a_catalog_file(self):
        # The mode is scoped to the file's absence. A component that *has* a
        # catalog-info.yaml is still held to every check — otherwise this input
        # would be a blanket off-switch for the policy.
        with policy_vars(
            skip_when_no_catalog_info="true",
            required_annotations="backstage.io/source-location",
            disallowed_annotations="backstage.io/skip-checks",
        ):
            present = finished_node(
                {
                    "catalog": {
                        "native": {
                            "backstage": {
                                "valid": True,
                                "metadata": {
                                    "annotations": {
                                        "backstage.io/skip-checks": "true"
                                    }
                                },
                                "spec": {"type": "service"},
                            }
                        }
                    }
                }
            )
            self.assertEqual(
                check_catalog_info_exists(present).status, CheckStatus.PASS
            )
            for check_fn in (check_owner_set, check_lifecycle_set, check_system_set):
                self.assertEqual(check_fn(present).status, CheckStatus.FAIL)
            # Configured checks still enforce: the required annotation is absent
            # and a disallowed one is present.
            self.assertEqual(
                check_required_annotations(present).status, CheckStatus.FAIL
            )
            self.assertEqual(
                check_disallowed_annotations(present).status, CheckStatus.FAIL
            )

    def test_set_still_pends_while_collectors_are_running(self):
        # Absent data is only "no catalog file" once the collector has finished.
        # Skipping earlier would resolve the check before the data could arrive.
        for name, check_fn, inputs in ALL_CHECKS:
            if DEFAULT_NO_CATALOG[name] == CheckStatus.PASS:
                continue  # deny-checks read defensively and never pend
            with self.subTest(check=name):
                with policy_vars(skip_when_no_catalog_info="true", **inputs):
                    check = check_fn(Node.from_component_json({}))
                    self.assertEqual(check.status, CheckStatus.PENDING)

    def test_input_truthiness(self):
        for raw, skips in [
            ("true", True),
            ("TRUE", True),
            ("  true  ", True),
            ("True", True),
            ("false", False),
            ("", False),
            ("yes", False),
            ("1", False),
        ]:
            with self.subTest(value=raw):
                with policy_vars(skip_when_no_catalog_info=raw):
                    check = check_owner_set(finished_node({}))
                    self.assertEqual(is_skipped(check), skips)


if __name__ == "__main__":
    unittest.main()
