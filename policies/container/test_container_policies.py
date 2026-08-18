"""Unit tests for the container policy checks.

The focus is the applicability boundary: a component with no containers must
resolve to SKIPPED (not a silent green PASS), while a component that genuinely
has Dockerfiles still passes/fails on the real assertions. The empty-vs-absent
distinction for `.containers.lint_results` is the subtle one — an empty array
means "hadolint ran and found nothing" (pass), absence means "no Dockerfiles"
(skip).
"""

import os
import unittest
from contextlib import contextmanager

from lunar_policy import Node, CheckStatus

from allowed_registries import main as check_allowed_registries
from build_tagged import main as check_build_tagged
from dockerfile_lint_clean import main as check_dockerfile_lint_clean
from healthcheck import main as check_healthcheck
from no_latest import main as check_no_latest
from required_labels import main as check_required_labels
from stable_tags import main as check_stable_tags
from user import main as check_user


ALL_CHECKS = [
    check_allowed_registries,
    check_build_tagged,
    check_dockerfile_lint_clean,
    check_healthcheck,
    check_no_latest,
    check_required_labels,
    check_stable_tags,
    check_user,
]


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


def finished_node(data):
    """Node with workflows marked finished.

    The SDK treats genuinely-absent data as no-data (PENDING) *while* collectors
    are still running, and only resolves it once workflows finish. Applicability
    skips are a post-collection judgement, so these tests use a finished node.
    """
    return Node.from_component_json(data, {"workflows_finished": True})


def definition(path="Dockerfile", **overrides):
    """A single valid `.containers.definitions[]` entry."""
    entry = {
        "path": path,
        "valid": True,
        "base_images": [{"reference": "alpine:3.19.1", "image": "alpine", "tag": "3.19.1"}],
        "final_stage": {"base_image": "alpine:3.19.1", "user": "nonroot", "has_healthcheck": True},
        "labels": {},
    }
    entry.update(overrides)
    return entry


class TestNoContainersSkips(unittest.TestCase):
    """A component with no container data at all must skip every check."""

    def test_empty_component_json_skips_every_check(self):
        for check in ALL_CHECKS:
            with self.subTest(check=check.__module__):
                with policy_vars(required_labels="org.opencontainers.image.source"):
                    result = check(finished_node({}))
                self.assertTrue(
                    is_skipped(result),
                    f"{result.name} did not skip on a component with no containers",
                )

    def test_unrelated_data_present_still_skips(self):
        """Other collectors having run doesn't make container checks applicable."""
        node = finished_node({"lang": {"go": {"version": "1.22"}}})
        for check in ALL_CHECKS:
            with self.subTest(check=check.__module__):
                with policy_vars(required_labels="org.opencontainers.image.source"):
                    self.assertTrue(is_skipped(check(node)))


class TestDockerfileLintClean(unittest.TestCase):
    def test_absent_lint_results_skips(self):
        check = check_dockerfile_lint_clean(finished_node({}))
        self.assertTrue(is_skipped(check))

    def test_empty_lint_results_passes(self):
        """Empty array = hadolint ran and found nothing. That is a real pass."""
        check = check_dockerfile_lint_clean(
            finished_node({"containers": {"lint_results": []}})
        )
        self.assertFalse(is_skipped(check))
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_clean_file_passes(self):
        data = {"containers": {"lint_results": [{"path": "Dockerfile", "issues": []}]}}
        check = check_dockerfile_lint_clean(finished_node(data))
        self.assertEqual(check.status, CheckStatus.PASS)

    def test_error_severity_fails(self):
        data = {"containers": {"lint_results": [{
            "path": "Dockerfile",
            "issues": [{"line": 3, "rule": "DL3006", "severity": "error", "message": "x"}],
        }]}}
        check = check_dockerfile_lint_clean(finished_node(data))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("DL3006", check.failure_reasons[0])

    def test_warning_below_default_threshold_passes(self):
        data = {"containers": {"lint_results": [{
            "path": "Dockerfile",
            "issues": [{"line": 3, "rule": "DL3008", "severity": "warning", "message": "x"}],
        }]}}
        self.assertEqual(
            check_dockerfile_lint_clean(finished_node(data)).status, CheckStatus.PASS
        )


class TestDefinitionChecks(unittest.TestCase):
    """The definition-gated checks still evaluate normally when Dockerfiles exist."""

    def test_no_latest_fails_on_latest_tag(self):
        data = {"containers": {"definitions": [definition(
            base_images=[{"reference": "alpine:latest", "image": "alpine", "tag": "latest"}]
        )]}}
        check = check_no_latest(finished_node(data))
        self.assertEqual(check.status, CheckStatus.FAIL)

    def test_no_latest_passes_on_pinned_tag(self):
        data = {"containers": {"definitions": [definition()]}}
        self.assertEqual(check_no_latest(finished_node(data)).status, CheckStatus.PASS)

    def test_stable_tags_fails_on_partial_version(self):
        data = {"containers": {"definitions": [definition(
            base_images=[{"reference": "node:20", "image": "node", "tag": "20"}]
        )]}}
        self.assertEqual(check_stable_tags(finished_node(data)).status, CheckStatus.FAIL)

    def test_user_fails_when_missing(self):
        data = {"containers": {"definitions": [definition(
            final_stage={"base_image": "alpine:3.19.1", "user": None, "has_healthcheck": True}
        )]}}
        self.assertEqual(check_user(finished_node(data)).status, CheckStatus.FAIL)

    def test_healthcheck_fails_when_missing(self):
        data = {"containers": {"definitions": [definition(
            final_stage={"base_image": "alpine:3.19.1", "user": "nonroot", "has_healthcheck": False}
        )]}}
        self.assertEqual(check_healthcheck(finished_node(data)).status, CheckStatus.FAIL)

    def test_allowed_registries_fails_on_disallowed(self):
        data = {"containers": {"definitions": [definition(
            base_images=[{"reference": "gcr.io/foo/bar:1.0.0", "image": "gcr.io/foo/bar", "tag": "1.0.0"}]
        )]}}
        with policy_vars(allowed_registries="docker.io"):
            check = check_allowed_registries(finished_node(data))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("gcr.io", check.failure_reasons[0])


class TestBuildTagged(unittest.TestCase):
    def test_no_builds_skips(self):
        """Dockerfiles present but no CI build observed — still not applicable."""
        data = {"containers": {"definitions": [definition()]}}
        self.assertTrue(is_skipped(check_build_tagged(finished_node(data))))

    def test_untagged_build_fails(self):
        data = {"containers": {"builds": [{"cmd": "docker build .", "has_tag": False}]}}
        self.assertEqual(check_build_tagged(finished_node(data)).status, CheckStatus.FAIL)

    def test_tagged_build_passes(self):
        data = {"containers": {"builds": [{"cmd": "docker build -t x:1.0.0 .", "has_tag": True}]}}
        self.assertEqual(check_build_tagged(finished_node(data)).status, CheckStatus.PASS)


class TestRequiredLabels(unittest.TestCase):
    def test_unconfigured_skips(self):
        data = {"containers": {"definitions": [definition()]}}
        self.assertTrue(is_skipped(check_required_labels(finished_node(data))))

    def test_missing_label_fails(self):
        data = {"containers": {"definitions": [definition()]}}
        with policy_vars(required_labels="org.opencontainers.image.source"):
            check = check_required_labels(finished_node(data))
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertIn("org.opencontainers.image.source", check.failure_reasons[0])

    def test_label_from_build_command_satisfies(self):
        data = {"containers": {
            "definitions": [definition()],
            "builds": [{
                "cmd": "docker build -t x:1.0.0 .",
                "has_tag": True,
                "dockerfile": "Dockerfile",
                "labels": {"org.opencontainers.image.source": "https://github.com/acme/x"},
            }],
        }}
        with policy_vars(required_labels="org.opencontainers.image.source"):
            self.assertEqual(
                check_required_labels(finished_node(data)).status, CheckStatus.PASS
            )


if __name__ == "__main__":
    unittest.main()
