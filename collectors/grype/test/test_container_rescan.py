#!/usr/bin/env python3
"""Tests for the grype container-scan / container-rescan collector.

container-rescan.sh resolves the image to scan out of the docker collector's
pushed-image record in Component JSON, fetched with `lunar component get-json`.
The regression these tests lock in: in PR context the script must pass
`--pr "$LUNAR_COMPONENT_PR"` (and `--git-sha "$LUNAR_COMPONENT_GIT_SHA"`) — the
Hub resolves an unqualified lookup to the default-branch snapshot
(`WHERE pr IS NULL`), so without the flags a PR run reads main's Component JSON,
never sees the image the PR pushed, and skips.

The mirror-image regression is just as important: on the default branch the
lookup must stay unpinned. The cron `container-rescan` gets a `head_sha`
dimension (the latest *ingested* main commit, which may not be collected yet) but
no `pr`, so pinning there would resolve nothing and silently stop the re-scan.

The `lunar` stub returns PR-scoped JSON only when `--pr` is present (mirroring
the Hub) and logs its calls to $CAPTURE; the real script runs as a subprocess
with a stubbed `grype`.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(__file__)
COLLECTOR = os.path.abspath(os.path.join(HERE, ".."))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="grype-test-")
        self.bin = os.path.join(self.tmp, "bin")
        self.mock = os.path.join(self.tmp, "mock")
        os.makedirs(self.bin)
        os.makedirs(self.mock)
        self.capture = os.path.join(self.tmp, "collect.log")
        self._write_stubs()
        # Defaults: both snapshots carry a pushed image, but *different* ones, so
        # which JSON the script read is visible in the scanned ref.
        self.fixture("main.json", self.MAIN_JSON)
        self.fixture("pr.json", self.PR_JSON)
        self.fixture("grype-results.json", self.GRYPE_RESULTS)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stub(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, 0o755)

    def _write_stubs(self):
        # lunar stub: `component get-json` returns the PR-scoped fixture only
        # when --pr is passed, else the default-branch fixture — exactly the
        # distinction the Hub makes. get-json calls are logged under GETJSON so
        # the test can assert on the exact flags; `collect` args and any piped
        # stdin are logged too.
        self._stub(
            "lunar",
            textwrap.dedent(
                """\
                #!/bin/sh
                if [ "$1" = "component" ] && [ "$2" = "get-json" ]; then
                  printf 'GETJSON: %s\\n' "$*" >> "$CAPTURE"
                  for a in "$@"; do
                    if [ "$a" = "--pr" ]; then cat "$MOCK_DIR/pr.json"; exit 0; fi
                  done
                  cat "$MOCK_DIR/main.json"
                  exit 0
                fi
                printf 'ARGS: %s\\n' "$*" >> "$CAPTURE"
                data="$(cat)"
                if [ -n "$data" ]; then printf 'STDIN: %s\\n' "$data" >> "$CAPTURE"; fi
                """
            ),
        )
        # grype stub: emit the canned scan results (the script redirects stdout
        # to its results file and reads the version back out of the JSON).
        self._stub(
            "grype",
            textwrap.dedent(
                """\
                #!/bin/sh
                printf 'GRYPE: %s\\n' "$*" >> "$CAPTURE"
                cat "$MOCK_DIR/grype-results.json"
                """
            ),
        )

    def fixture(self, name, content):
        with open(os.path.join(self.mock, name), "w") as f:
            f.write(content)

    def run_script(self, env):
        full_env = {
            "PATH": self.bin + ":" + os.environ["PATH"],
            "MOCK_DIR": self.mock,
            "CAPTURE": self.capture,
        }
        full_env.update(env)
        result = subprocess.run(
            ["bash", os.path.join(COLLECTOR, "container-rescan.sh")],
            env=full_env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        log = ""
        if os.path.exists(self.capture):
            with open(self.capture) as f:
                log = f.read()
        return result, log

    @staticmethod
    def getjson_calls(log):
        return [ln for ln in log.splitlines() if ln.startswith("GETJSON:")]

    @staticmethod
    def collected(log, path):
        """The payload the script wrote to `path` via `lunar collect -j <path> -`."""
        lines = log.splitlines()
        for i, ln in enumerate(lines):
            if ln.startswith("ARGS:") and f" {path} " in ln + " ":
                for nxt in lines[i + 1 :]:
                    if nxt.startswith("STDIN: "):
                        return json.loads(nxt[len("STDIN: ") :])
                    if nxt.startswith("ARGS:"):
                        break
        return None

    MAIN_IMAGE = "earthly/lunar-hub:main-abc123"
    PR_IMAGE = "earthly/lunar-hub:pr-2151"

    MAIN_JSON = json.dumps(
        {"containers": {"native": {"docker": {"cicd": {"cmds": [
            {"cmd": f"docker push {MAIN_IMAGE}"}]}}}}}
    )
    PR_JSON = json.dumps(
        {"containers": {"native": {"docker": {"cicd": {"cmds": [
            {"cmd": f"docker push {PR_IMAGE}"}]}}}}}
    )
    # Built but never pushed — nothing shipped, so nothing to scan.
    NO_PUSH_JSON = json.dumps(
        {"containers": {"native": {"docker": {"cicd": {"cmds": [
            {"cmd": "docker build -t earthly/lunar-hub:local ."}]}}}}}
    )

    GRYPE_RESULTS = json.dumps({
        "descriptor": {"version": "0.87.0"},
        "distro": {"name": "debian", "version": "12"},
        "matches": [{
            "vulnerability": {
                "id": "CVE-2026-0001", "severity": "High",
                "description": "curl flaw",
                "fix": {"state": "fixed", "versions": ["8.2.0"]},
            },
            "artifact": {"name": "curl", "version": "8.1.0", "type": "deb"},
        }],
    })

    # An after-json run on a PR: the Hub sets both dimensions.
    PR_ENV = {
        "LUNAR_COMPONENT_ID": "github.com/acme/backend",
        "LUNAR_COLLECTOR_NAME": "grype.container-scan",
        "LUNAR_COMPONENT_PR": "2151",
        "LUNAR_COMPONENT_GIT_SHA": "bb0707e34",
    }
    # The cron re-scan: head_sha is set, pr is not.
    CRON_ENV = {
        "LUNAR_COMPONENT_ID": "github.com/acme/backend",
        "LUNAR_COLLECTOR_NAME": "grype.container-rescan",
        "LUNAR_COMPONENT_GIT_SHA": "deadbeef",
    }


class PRScopedLookupTest(Base):
    def test_pr_run_scans_the_image_this_pr_pushed(self):
        # The fix: pin get-json to (sha, pr) so the PR's own pushed image is
        # found. Pre-fix this read main's JSON and scanned MAIN_IMAGE instead.
        result, log = self.run_script(dict(self.PR_ENV))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        calls = self.getjson_calls(log)
        self.assertEqual(len(calls), 1, msg=log)
        self.assertIn("--pr 2151", calls[0])
        self.assertIn("--git-sha bb0707e34", calls[0])
        self.assertIn(f"Scanning image: {self.PR_IMAGE}", result.stderr)
        self.assertNotIn(self.MAIN_IMAGE, result.stderr)
        scan = self.collected(log, ".container_scan")
        self.assertIsNotNone(scan, msg=log)
        self.assertEqual(scan["image"], self.PR_IMAGE)
        self.assertEqual(scan["source"]["integration"], "after-json")

    def test_pr_without_sha_still_narrows_to_the_pr(self):
        # head_sha absent but pr set: degrade to --pr alone rather than falling
        # back to the default-branch snapshot.
        env = dict(self.PR_ENV)
        del env["LUNAR_COMPONENT_GIT_SHA"]
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        call = self.getjson_calls(log)[0]
        self.assertIn("--pr 2151", call)
        self.assertNotIn("--git-sha", call)
        self.assertIn(f"Scanning image: {self.PR_IMAGE}", result.stderr)


class DefaultBranchLookupTest(Base):
    def test_cron_run_is_not_pinned(self):
        # AC: the cron / default-branch path must keep the unqualified lookup.
        # Its head_sha is the latest ingested main commit, which may have no
        # collected snapshot — pinning to it would resolve nothing and stop the
        # re-scan. So --git-sha must NOT be passed just because it is set.
        result, log = self.run_script(dict(self.CRON_ENV))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        calls = self.getjson_calls(log)
        self.assertEqual(len(calls), 1, msg=log)
        self.assertNotIn("--git-sha", calls[0])
        self.assertNotIn("--pr", calls[0])
        self.assertIn(f"Scanning image: {self.MAIN_IMAGE}", result.stderr)
        scan = self.collected(log, ".container_scan")
        self.assertEqual(scan["image"], self.MAIN_IMAGE)
        self.assertEqual(scan["source"]["integration"], "cron")

    def test_after_json_push_to_main_is_not_pinned(self):
        # An after-json run on a main push has head_sha but no pr: default-branch
        # latest is already the commit being scanned, so leave it unpinned.
        env = dict(self.CRON_ENV, LUNAR_COLLECTOR_NAME="grype.container-scan")
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("--git-sha", self.getjson_calls(log)[0])
        self.assertIn(f"Scanning image: {self.MAIN_IMAGE}", result.stderr)


class SkipSafetyTest(Base):
    def test_skips_cleanly_when_nothing_was_pushed(self):
        # Built but not pushed: no image shipped, so skip without failing the run
        # and without writing .container_scan.
        self.fixture("main.json", self.NO_PUSH_JSON)
        result, log = self.run_script(dict(self.CRON_ENV))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("No pushed container image to scan", result.stderr)
        self.assertIsNone(self.collected(log, ".container_scan"))

    def test_skips_cleanly_when_get_json_returns_nothing(self):
        # get-json failing (or resolving no snapshot) must not fail the run.
        self._stub("lunar", "#!/bin/sh\nexit 1\n")
        result, _ = self.run_script(dict(self.CRON_ENV))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("No pushed container image to scan", result.stderr)

    def test_container_image_input_bypasses_get_json(self):
        # An explicitly pinned image needs no Component JSON lookup at all.
        env = dict(self.PR_ENV, LUNAR_VAR_CONTAINER_IMAGE="ghcr.io/acme/api:v1")
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self.getjson_calls(log), [])
        self.assertIn("Scanning image: ghcr.io/acme/api:v1", result.stderr)


class MultiImageTest(Base):
    """Every distinct pushed ref is scanned; the blob keeps its single-image
    fields for the primary (last pushed) image and adds per-image detail."""

    IMAGES = [
        "earthly/lunar-hub:abc12345",
        "earthly/lunar-dashboards:abc12345",
        "earthly/lunar-snippet-init:abc12345",
    ]
    MULTI_JSON = json.dumps(
        {"containers": {"native": {"docker": {"cicd": {"cmds": [
            {"cmd": f"docker build -t {IMAGES[0]} ."},
            {"cmd": f"docker push {IMAGES[0]}"},
            {"cmd": f"docker push {IMAGES[1]}"},
            {"cmd": f"docker push {IMAGES[0]}"},  # same ref pushed twice: one scan
            {"cmd": f"docker buildx build --push -t {IMAGES[2]} ."},
        ]}}}}}
    )

    @staticmethod
    def scanned_refs(log):
        return [ln.split()[1] for ln in log.splitlines() if ln.startswith("GRYPE:")]

    def failing_scanner(self, bad_ref):
        self._stub(
            "grype",
            "#!/bin/sh\n"
            "printf 'GRYPE: %s\\n' \"$*\" >> \"$CAPTURE\"\n"
            f"if [ \"$1\" = \"{bad_ref}\" ]; then echo \"failed to pull image: unauthorized\" >&2; exit 1; fi\n"
            "cat \"$MOCK_DIR/grype-results.json\"\n",
        )

    def test_scans_every_pushed_image_once_in_push_order(self):
        self.fixture("main.json", self.MULTI_JSON)
        result, log = self.run_script(dict(self.CRON_ENV))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self.scanned_refs(log), self.IMAGES)
        for ref in self.IMAGES:
            self.assertIn(f"Scanning image: {ref}", result.stderr)
        scan = self.collected(log, ".container_scan")
        self.assertIsNotNone(scan, msg=log)
        # Primary = the most recently pushed image, exactly what `| last` picked before.
        self.assertEqual(scan["image"], self.IMAGES[2])
        self.assertEqual(scan["os"], {"family": "debian", "version": "12"})
        self.assertEqual([i["image"] for i in scan["images"]], self.IMAGES)
        self.assertTrue(all(i["tool"] == "grype" for i in scan["images"]))
        self.assertEqual(scan["images"][0]["vulnerabilities"]["total"], 1)
        # Counts, findings and summary span every image.
        self.assertEqual(scan["vulnerabilities"], {"critical": 0, "high": 3, "medium": 0, "low": 0, "total": 3})
        self.assertEqual([f["image"] for f in scan["findings"]], self.IMAGES)
        self.assertTrue(scan["summary"]["has_high"])
        self.assertNotIn("errors", scan)
        # Raw native output is kept for the primary image only.
        self.assertEqual(len(self.collected(log, ".container_scan.native.grype.matches")), 1)

    def test_single_image_blob_keeps_its_shape(self):
        # One pushed image: the same top-level fields as before, plus images[].
        result, log = self.run_script(dict(self.CRON_ENV))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        scan = self.collected(log, ".container_scan")
        self.assertEqual(scan["image"], self.MAIN_IMAGE)
        self.assertEqual(scan["vulnerabilities"], {"critical": 0, "high": 1, "medium": 0, "low": 0, "total": 1})
        self.assertEqual(scan["summary"], {"has_critical": False, "has_high": True, "all_fixable": True})
        self.assertEqual([i["image"] for i in scan["images"]], [self.MAIN_IMAGE])
        self.assertEqual(scan["findings"][0]["image"], self.MAIN_IMAGE)
        self.assertEqual(scan["findings"][0]["cve"], "CVE-2026-0001")

    def test_one_failing_image_is_recorded_and_the_rest_still_scan(self):
        self.fixture("main.json", self.MULTI_JSON)
        self.failing_scanner(self.IMAGES[1])
        result, log = self.run_script(dict(self.CRON_ENV))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn(f"Grype image scan failed for {self.IMAGES[1]}", result.stderr)
        scan = self.collected(log, ".container_scan")
        self.assertEqual([i["image"] for i in scan["images"]], [self.IMAGES[0], self.IMAGES[2]])
        self.assertEqual(scan["errors"], [{"image": self.IMAGES[1], "error": "failed to pull image: unauthorized"}])
        self.assertEqual(scan["vulnerabilities"]["total"], 2)
        self.assertEqual(scan["image"], self.IMAGES[2])
        self.assertIn("2 scanned image(s); 1 could not be scanned", result.stderr)

    def test_nothing_is_written_when_no_image_could_be_scanned(self):
        self.failing_scanner(self.MAIN_IMAGE)
        result, log = self.run_script(dict(self.CRON_ENV))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("could not scan any", result.stderr)
        self.assertIsNone(self.collected(log, ".container_scan"))

    def test_container_image_input_accepts_a_list(self):
        env = dict(self.CRON_ENV, LUNAR_VAR_CONTAINER_IMAGE="ghcr.io/acme/api:v1, ghcr.io/acme/worker:v1")
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self.getjson_calls(log), [])
        self.assertEqual(self.scanned_refs(log), ["ghcr.io/acme/api:v1", "ghcr.io/acme/worker:v1"])
        scan = self.collected(log, ".container_scan")
        self.assertEqual(scan["image"], "ghcr.io/acme/worker:v1")
        self.assertEqual([i["image"] for i in scan["images"]], ["ghcr.io/acme/api:v1", "ghcr.io/acme/worker:v1"])


class ProvenanceTest(Base):
    """`.container_scan` must say WHEN it was collected and WHAT bytes it scanned.

    Without those, a re-scan that never refreshed this commit is
    indistinguishable from a fresh one: the release page renders a five-day-old
    count as current (ENG-1811). `collected_at` dates the payload;
    `collected_sha` names the commit the run was bound to; the resolved registry
    digest is the only field that ties the numbers to an actual artifact — the
    recorded ref is a floating tag.
    """

    DIGEST = "sha256:" + "a" * 64
    OTHER_DIGEST = "sha256:" + "c" * 64

    def with_repo_digests(self, repo_digests):
        """Re-emit the canned scan results with the registry's repo digests."""
        results = json.loads(self.GRYPE_RESULTS)
        results["source"] = {"type": "image", "target": {
            "userInput": self.MAIN_IMAGE, "repoDigests": repo_digests}}
        self.fixture("grype-results.json", json.dumps(results))

    def scan(self, env=None):
        result, log = self.run_script(dict(env or self.CRON_ENV))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        scan = self.collected(log, ".container_scan")
        self.assertIsNotNone(scan, msg=log)
        return scan

    def test_source_is_dated_and_names_the_commit_it_ran_at(self):
        source = self.scan()["source"]
        self.assertRegex(source["collected_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(source["collected_sha"], "deadbeef")

    def test_collected_sha_is_omitted_when_the_runtime_sets_none(self):
        env = dict(self.CRON_ENV)
        del env["LUNAR_COMPONENT_GIT_SHA"]
        source = self.scan(env)["source"]
        self.assertNotIn("collected_sha", source)
        self.assertIn("collected_at", source)

    def test_digest_is_recorded_for_the_primary_image_and_per_image(self):
        self.with_repo_digests(["earthly/lunar-hub@" + self.DIGEST])
        scan = self.scan()
        self.assertEqual(scan["digest"], self.DIGEST)
        self.assertEqual(scan["images"][0]["digest"], self.DIGEST)
        # The floating ref is still recorded — the digest is added alongside it.
        self.assertEqual(scan["image"], self.MAIN_IMAGE)

    def test_the_digest_matching_the_scanned_repo_wins(self):
        self.with_repo_digests(["someone/else@" + self.OTHER_DIGEST,
                                "earthly/lunar-hub@" + self.DIGEST])
        self.assertEqual(self.scan()["digest"], self.DIGEST)

    def test_no_digest_is_invented_when_the_registry_reports_none(self):
        # The stock fixture has no repo digests at all (a local-only image).
        scan = self.scan()
        self.assertNotIn("digest", scan)
        self.assertNotIn("digest", scan["images"][0])

    def test_ambiguous_repo_digests_are_left_unresolved(self):
        # Several digests, none for the repo scanned: recording either would
        # claim the scan covered bytes it never saw.
        self.with_repo_digests(["someone/else@" + self.OTHER_DIGEST,
                                "third/party@sha256:" + "d" * 64])
        self.assertNotIn("digest", self.scan())

    def test_a_malformed_repo_digest_is_rejected(self):
        self.with_repo_digests(["earthly/lunar-hub@notadigest"])
        self.assertNotIn("digest", self.scan())


class ScanHistoryTest(Base):
    """`container_scan_history_size` keeps a bounded audit trail of past scans.

    Mirrors `.sca.history[]`: cron-only (its record is replaced wholesale, so
    the array cannot self-concatenate), counts + provenance only, and a read
    failure skips the re-scan rather than writing a record that would wipe the
    trail.
    """

    PRIOR_DIGEST = "sha256:" + "b" * 64
    PRIOR_SCAN = {
        "source": {"tool": "grype", "integration": "after-json",
                   "collected_at": "2026-09-10T03:00:00Z", "collected_sha": "cafe1234"},
        "image": "earthly/lunar-hub:main-old",
        "digest": PRIOR_DIGEST,
        "vulnerabilities": {"critical": 1, "high": 2, "medium": 0, "low": 0, "total": 3},
        "summary": {"has_critical": True, "has_high": True, "all_fixable": False},
        # The arrays the hub concatenates across collectors — snapshotting these
        # would double them on every re-scan.
        "findings": [{"cve": "CVE-2026-OLD", "image": "earthly/lunar-hub:main-old"}],
        "images": [{"image": "earthly/lunar-hub:main-old", "tool": "grype"}],
        "native": {"grype": {"matches": [1, 2, 3]}},
    }

    def main_with_scan(self, scan):
        self.fixture("main.json", json.dumps({
            "containers": {"native": {"docker": {"cicd": {"cmds": [
                {"cmd": f"docker push {self.MAIN_IMAGE}"}]}}}},
            "container_scan": scan,
        }))

    def run_ok(self, env):
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return result, log

    def test_history_is_off_by_default(self):
        self.main_with_scan(self.PRIOR_SCAN)
        _, log = self.run_ok(dict(self.CRON_ENV))
        self.assertNotIn("history", self.collected(log, ".container_scan"))

    def test_the_previous_scan_is_snapshotted_with_its_provenance(self):
        self.main_with_scan(self.PRIOR_SCAN)
        env = dict(self.CRON_ENV, LUNAR_VAR_CONTAINER_SCAN_HISTORY_SIZE="5")
        _, log = self.run_ok(env)
        scan = self.collected(log, ".container_scan")
        self.assertEqual(scan["history"], [{
            "source": self.PRIOR_SCAN["source"],
            "image": "earthly/lunar-hub:main-old",
            "digest": self.PRIOR_DIGEST,
            "vulnerabilities": self.PRIOR_SCAN["vulnerabilities"],
            "summary": self.PRIOR_SCAN["summary"],
        }])
        # The live fields are this run's, not the snapshot's.
        self.assertEqual(scan["vulnerabilities"]["total"], 1)
        self.assertEqual(scan["source"]["integration"], "cron")

    def test_the_snapshot_omits_the_arrays_the_hub_concatenates(self):
        self.main_with_scan(self.PRIOR_SCAN)
        env = dict(self.CRON_ENV, LUNAR_VAR_CONTAINER_SCAN_HISTORY_SIZE="5")
        _, log = self.run_ok(env)
        entry = self.collected(log, ".container_scan")["history"][0]
        for concatenated in ("findings", "images", "native", "history"):
            self.assertNotIn(concatenated, entry)

    def test_history_is_bounded_and_keeps_the_oldest_entry(self):
        prior = dict(self.PRIOR_SCAN, history=[
            {"source": {"integration": "code", "collected_at": f"2026-09-0{i}T03:00:00Z"}}
            for i in range(1, 5)
        ])
        self.main_with_scan(prior)
        env = dict(self.CRON_ENV, LUNAR_VAR_CONTAINER_SCAN_HISTORY_SIZE="3")
        _, log = self.run_ok(env)
        history = self.collected(log, ".container_scan")["history"]
        self.assertEqual(len(history), 3)
        # The first scan on record (the release-time one) survives; the
        # second-oldest is what gets dropped.
        self.assertEqual(history[0]["source"]["collected_at"], "2026-09-01T03:00:00Z")
        self.assertEqual(history[1]["source"]["collected_at"], "2026-09-04T03:00:00Z")
        self.assertEqual(history[2]["image"], "earthly/lunar-hub:main-old")

    def test_no_history_key_when_there_is_nothing_to_snapshot(self):
        # First ever scan: an empty array would be noise.
        env = dict(self.CRON_ENV, LUNAR_VAR_CONTAINER_SCAN_HISTORY_SIZE="3")
        _, log = self.run_ok(env)
        self.assertNotIn("history", self.collected(log, ".container_scan"))

    def test_the_on_push_scan_never_writes_history(self):
        # An after-json record is concatenated, not replaced, so a history[] on
        # it would grow without bound on every push. Run it on the default
        # branch, where it reads the very Component JSON the cron reads — then
        # the cron-only fence is the only thing keeping history out of it. (A PR
        # run would pass vacuously: its PR-scoped snapshot has no prior scan.)
        self.main_with_scan(self.PRIOR_SCAN)
        env = dict(
            self.CRON_ENV,
            LUNAR_COLLECTOR_NAME=self.CRON_ENV["LUNAR_COLLECTOR_NAME"].replace(
                "container-rescan", "container-scan"),
            LUNAR_VAR_CONTAINER_SCAN_HISTORY_SIZE="5",
        )
        _, log = self.run_ok(env)
        scan = self.collected(log, ".container_scan")
        self.assertEqual(scan["source"]["integration"], "after-json")
        self.assertNotIn("history", scan)

    def test_a_pinned_image_still_reads_the_component_json_for_history(self):
        self.main_with_scan(self.PRIOR_SCAN)
        env = dict(self.CRON_ENV, LUNAR_VAR_CONTAINER_IMAGE="ghcr.io/acme/api:v1",
                   LUNAR_VAR_CONTAINER_SCAN_HISTORY_SIZE="5")
        _, log = self.run_ok(env)
        self.assertEqual(len(self.getjson_calls(log)), 1, msg=log)
        self.assertEqual(len(self.collected(log, ".container_scan")["history"]), 1)

    def test_a_pinned_image_reads_nothing_when_history_is_off(self):
        env = dict(self.CRON_ENV, LUNAR_VAR_CONTAINER_IMAGE="ghcr.io/acme/api:v1")
        _, log = self.run_ok(env)
        self.assertEqual(self.getjson_calls(log), [])

    def test_an_unreadable_component_json_skips_instead_of_wiping_history(self):
        # The cron record is replaced wholesale: writing one without history
        # destroys the trail. Skip, keep the last good record, retry next tick.
        self._stub(
            "lunar",
            "#!/bin/sh\n"
            "if [ \"$1\" = \"component\" ]; then printf 'GETJSON: %s\\n' \"$*\" >> \"$CAPTURE\"; exit 1; fi\n"
            "printf 'ARGS: %s\\n' \"$*\" >> \"$CAPTURE\"\n",
        )
        env = dict(self.CRON_ENV, LUNAR_VAR_CONTAINER_IMAGE="ghcr.io/acme/api:v1",
                   LUNAR_VAR_CONTAINER_SCAN_HISTORY_SIZE="5")
        result, log = self.run_ok(env)
        self.assertIn("skipping this re-scan", result.stderr)
        self.assertIsNone(self.collected(log, ".container_scan"))
        # It bails before paying for the scan, too.
        self.assertNotIn("Scanning image:", result.stderr)

    def test_carried_forward_duplicates_are_collapsed(self):
        # A component running both scanners' crons has two cron records, so the
        # merged history each one reads holds the other's entries as well.
        # Without the dedupe every record would re-absorb and re-emit them.
        dup = {"source": {"tool": "other", "integration": "cron",
                          "collected_at": "2026-09-02T03:00:00Z"}}
        prior = dict(self.PRIOR_SCAN, history=[dup, dup, dup])
        self.main_with_scan(prior)
        env = dict(self.CRON_ENV, LUNAR_VAR_CONTAINER_SCAN_HISTORY_SIZE="5")
        _, log = self.run_ok(env)
        history = self.collected(log, ".container_scan")["history"]
        self.assertEqual(len(history), 2, msg=history)
        self.assertEqual(history[0], dup)
        self.assertEqual(history[1]["image"], "earthly/lunar-hub:main-old")

    def test_a_non_numeric_history_size_is_treated_as_off(self):
        self.main_with_scan(self.PRIOR_SCAN)
        env = dict(self.CRON_ENV, LUNAR_VAR_CONTAINER_SCAN_HISTORY_SIZE="lots")
        _, log = self.run_ok(env)
        self.assertNotIn("history", self.collected(log, ".container_scan"))

if __name__ == "__main__":
    unittest.main()
