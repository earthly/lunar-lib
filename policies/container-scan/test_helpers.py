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

import max_total  # noqa: E402
from helpers import pushed_image_refs, pushed_ref  # noqa: E402


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
        self.assertIn("No container scanning data found", c.failure_reasons[0])


if __name__ == "__main__":
    unittest.main()
