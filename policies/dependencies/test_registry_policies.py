"""Unit tests for the registry-provenance policies."""

import unittest

from lunar_policy import CheckStatus, Node

from approved_registries import check_approved_registries
from no_public_registries import check_no_public_registries

FINISHED = {"workflows_finished": True}


def component(*registries):
    return {"dependencies": {"registries": list(registries)}}


def entry(host, ecosystem="npm", kind="primary", is_default=False,
          is_public=False, path=".npmrc", name=None):
    e = {
        "ecosystem": ecosystem,
        "host": host,
        "kind": kind,
        "path": path,
        "is_default": is_default,
        "is_public": is_public,
    }
    if name:
        e["name"] = name
    return e


def results(check):
    """Raw results — Check.status reports a pure skip as PASS."""
    return [r.result for r in check._results]


class TestApprovedRegistries(unittest.TestCase):
    def test_allowed_host_passes(self):
        node = Node.from_component_json(
            component(entry("dl.cloudsmith.io")), FINISHED
        )
        check = check_approved_registries("dl.cloudsmith.io", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_disallowed_host_fails(self):
        node = Node.from_component_json(
            component(entry("registry.npmjs.org", is_public=True)), FINISHED
        )
        check = check_approved_registries("dl.cloudsmith.io", node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_implicit_default_fails_with_explanatory_message(self):
        """The case the collector exists to catch: no registry configured."""
        node = Node.from_component_json(
            component(entry("registry.npmjs.org", is_default=True,
                            is_public=True, path="package.json")),
            FINISHED,
        )
        check = check_approved_registries("dl.cloudsmith.io", node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        message = check._results[0].failure_message
        self.assertIn("ecosystem default", message)
        self.assertIn("no registry configured in package.json", message)
        self.assertIn("dl.cloudsmith.io", message)

    def test_publish_target_is_ignored(self):
        """Publishing to Maven Central is not a dependency source."""
        node = Node.from_component_json(
            component(entry("repo.maven.apache.org", ecosystem="maven",
                            kind="publish", is_public=True, path="pom.xml")),
            FINISHED,
        )
        check = check_approved_registries("dl.cloudsmith.io", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_host_match_is_case_insensitive(self):
        node = Node.from_component_json(
            component(entry("DL.Cloudsmith.IO")), FINISHED
        )
        check = check_approved_registries("dl.cloudsmith.io", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_multiple_allowed_registries(self):
        node = Node.from_component_json(
            component(entry("nexus.acme.com"), entry("dl.cloudsmith.io")), FINISHED
        )
        check = check_approved_registries("dl.cloudsmith.io, nexus.acme.com", node=node)
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_each_offender_reported_separately(self):
        node = Node.from_component_json(
            component(
                entry("registry.npmjs.org", is_public=True),
                entry("pypi.org", ecosystem="pip", is_public=True,
                      path="requirements.txt"),
            ),
            FINISHED,
        )
        check = check_approved_registries("dl.cloudsmith.io", node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(len([r for r in results(check) if r == CheckStatus.FAIL]), 2)

    def test_empty_allowlist_is_a_misconfiguration(self):
        """An empty allow-list would fail every component — surface it as an
        error rather than silently passing. Matches the container policy's
        allowed-registries behaviour."""
        node = Node.from_component_json(component(entry("anything")), FINISHED)
        with self.assertRaises(ValueError) as ctx:
            check_approved_registries("", node=node)
        self.assertIn("allowed_registries", str(ctx.exception))

    def test_missing_data_skips_after_collection(self):
        node = Node.from_component_json({}, FINISHED)
        check = check_approved_registries("dl.cloudsmith.io", node=node)
        self.assertIn(CheckStatus.SKIPPED, results(check))

    def test_missing_data_pends_during_collection(self):
        """Still collecting is not the same as no package manager."""
        node = Node.from_component_json({}, {"workflows_finished": False})
        check = check_approved_registries("dl.cloudsmith.io", node=node)
        self.assertEqual(check.status, CheckStatus.PENDING)


class TestNoPublicRegistries(unittest.TestCase):
    def test_internal_registry_passes(self):
        node = Node.from_component_json(
            component(entry("dl.cloudsmith.io")), FINISHED
        )
        self.assertEqual(check_no_public_registries(node=node).status, CheckStatus.PASS)

    def test_public_registry_fails(self):
        node = Node.from_component_json(
            component(entry("registry.npmjs.org", is_public=True)), FINISHED
        )
        check = check_no_public_registries(node=node)
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("public package index", check._results[0].failure_message)

    def test_needs_no_configuration(self):
        node = Node.from_component_json(
            component(entry("pypi.org", ecosystem="pip", is_public=True,
                            path="requirements.txt")),
            FINISHED,
        )
        self.assertEqual(check_no_public_registries(node=node).status, CheckStatus.FAIL)

    def test_publish_target_is_ignored(self):
        node = Node.from_component_json(
            component(entry("repo.maven.apache.org", ecosystem="maven",
                            kind="publish", is_public=True, path="pom.xml")),
            FINISHED,
        )
        self.assertEqual(check_no_public_registries(node=node).status, CheckStatus.PASS)

    def test_missing_data_skips_after_collection(self):
        node = Node.from_component_json({}, FINISHED)
        self.assertIn(CheckStatus.SKIPPED, results(check_no_public_registries(node=node)))

    def test_missing_data_pends_during_collection(self):
        node = Node.from_component_json({}, {"workflows_finished": False})
        check = check_no_public_registries(node=node)
        self.assertEqual(check.status, CheckStatus.PENDING)


if __name__ == "__main__":
    unittest.main(verbosity=2)
