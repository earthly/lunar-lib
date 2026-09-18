"""Unit tests for the container-scan applicability helpers (helpers.py).

`.containers` exists on almost every commit — the CI tracer records a bare
`docker info` into it — so "was an image shipped?" has to come from the pushed
refs in the docker record. These prove the resolution matches the one
`container-rescan.sh` uses to choose images, and that both checks skip rather
than fail when nothing shipped.
"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunar_policy import Node, CheckStatus  # noqa: E402

import executed  # noqa: E402
import max_total  # noqa: E402
from helpers import (  # noqa: E402
    no_scan_data_reasons,
    pushed_image_refs,
    pushed_ref,
)


def node(cmds=None, container_scan=None):
    data = {"containers": {"native": {"docker": {"cicd": {"cmds": cmds or []}}}}}
    if container_scan is not None:
        data["container_scan"] = container_scan
    return Node.from_component_json(data, bundle_info={"workflows_finished": True})


def resolved_status(c):
    for r in getattr(c, "_results", []):
        if r.result == CheckStatus.SKIPPED:
            return CheckStatus.SKIPPED
    return c.status


class PushedRefTests(unittest.TestCase):
    def test_recognises_a_push(self):
        self.assertEqual(
            pushed_ref("docker push registry.example.com/app:1.2.3"),
            "registry.example.com/app:1.2.3",
        )

    def test_recognises_a_build_that_pushes(self):
        for cmd in (
            "docker build --push -t registry.example.com/app:1.2.3 .",
            "docker buildx build --push --tag registry.example.com/app:1.2.3 .",
        ):
            self.assertEqual(pushed_ref(cmd), "registry.example.com/app:1.2.3", cmd)

    def test_ci_tracer_plumbing_is_not_a_push(self):
        for cmd in (
            "docker info",
            "docker info --format={{.DockerRootDir}}",
            "docker ps",
            "docker container inspect earthly-buildkitd",
            "docker image inspect docker.io/earthly/buildkitd:v0.8.16",
            "docker exec -i earthly-buildkitd buildctl dial-stdio",
            "docker build -t registry.example.com/app:1.2.3 .",
            "",
        ):
            self.assertIsNone(pushed_ref(cmd), cmd)


class PushedImageRefsTests(unittest.TestCase):
    def test_counts_each_ref_once_in_push_order(self):
        refs = pushed_image_refs(
            node(
                [
                    {"cmd": "docker info"},
                    {"cmd": "docker push example.com/b:1"},
                    {"cmd": "docker push example.com/a:1"},
                    {"cmd": "docker push example.com/b:1"},
                ]
            ).get_node(".containers")
        )
        self.assertEqual(refs, ["example.com/b:1", "example.com/a:1"])

    def test_no_docker_record_at_all(self):
        n = Node.from_component_json(
            {"containers": {"definitions": []}},
            bundle_info={"workflows_finished": True},
        )
        self.assertEqual(pushed_image_refs(n.get_node(".containers")), [])


class MaxTotalApplicabilityTests(unittest.TestCase):
    """max-total shares the gate, so it moves with max-severity."""

    def run_check(self, n):
        os.environ["LUNAR_VAR_max_total_threshold"] = "5"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return max_total.main(node=n)
        finally:
            del os.environ["LUNAR_VAR_max_total_threshold"]

    def test_skips_when_nothing_was_pushed(self):
        c = self.run_check(node([{"cmd": "docker info"}, {"cmd": "docker ps"}]))
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)
        self.assertIn("No container image was pushed", c._results[0].failure_message)

    def test_fails_when_an_image_was_pushed_and_not_scanned(self):
        c = self.run_check(node([{"cmd": "docker push example.com/a:1"}]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertIn("No container scan results at this commit", c.failure_reasons[0])
        self.assertEqual(c.failure_reasons[1], "not scanned: example.com/a:1")


class NoScanDataMessageTests(unittest.TestCase):
    """What the checks say when `.container_scan` is absent.

    The line this replaced — "Ensure a scanner (Trivy, Grype, etc.) is
    configured" — sent readers looking for a configuration gap on an install
    where both scanners were configured, ran, and recorded nothing for the
    commit. Neither reading is assumed now, and the images that have no results
    are named.
    """

    def test_names_every_unscanned_image(self):
        reasons = no_scan_data_reasons(["example.com/a:1", "example.com/b:1"])
        self.assertIn("though it pushed 2 image(s)", reasons[0])
        self.assertEqual(reasons[1:], ["not scanned: example.com/a:1", "not scanned: example.com/b:1"])

    def test_does_not_blame_configuration_alone(self):
        for reasons in (no_scan_data_reasons([]), no_scan_data_reasons(["example.com/a:1"])):
            self.assertNotIn("Ensure a scanner", reasons[0])
            self.assertIn("or a configured one recorded nothing here", reasons[0])

    def test_says_nothing_about_pushes_when_there_were_none(self):
        # `executed` fails a commit with no pushed image at all, so the headline
        # has to read correctly with an empty list.
        reasons = no_scan_data_reasons([])
        self.assertEqual(len(reasons), 1)
        self.assertNotIn("pushed", reasons[0])


class ExecutedTests(unittest.TestCase):
    """`executed` gates on `.containers` alone — it asks whether a scan was owed."""

    def run_check(self, n):
        with contextlib.redirect_stdout(io.StringIO()):
            return executed.main(node=n)

    def test_skips_without_containers(self):
        n = Node.from_component_json({}, bundle_info={"workflows_finished": True})
        c = self.run_check(n)
        self.assertEqual(resolved_status(c), CheckStatus.SKIPPED)

    def test_fails_and_names_the_unscanned_image(self):
        c = self.run_check(node([{"cmd": "docker push example.com/a:1"}]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertEqual(c.failure_reasons[1], "not scanned: example.com/a:1")

    def test_still_fails_when_nothing_was_pushed(self):
        # Unlike max-severity/max-total, a commit that pushed nothing but has a
        # docker record still owes a scan here.
        c = self.run_check(node([{"cmd": "docker info"}]))
        self.assertEqual(resolved_status(c), CheckStatus.FAIL)
        self.assertEqual(len(c.failure_reasons), 1)

    def test_passes_when_a_scan_exists(self):
        c = self.run_check(node([{"cmd": "docker push example.com/a:1"}], container_scan={"image": "example.com/a:1"}))
        self.assertEqual(resolved_status(c), CheckStatus.PASS)


if __name__ == "__main__":
    unittest.main()
