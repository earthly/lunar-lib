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
        self.fixture("no-push.json", self.NO_PUSH_JSON)
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
                  # Test seams, both off by default. Each names a countdown file
                  # holding the number of remaining calls that should misbehave;
                  # -1 means forever. This is how the Hub's mat lag is modelled:
                  # the read either fails outright (the sha's row has not
                  # materialized) or succeeds while still missing the push
                  # record that dispatched the wave.
                  if [ -n "$GETJSON_FAIL" ] && [ -f "$GETJSON_FAIL" ]; then
                    n=$(cat "$GETJSON_FAIL")
                    if [ "$n" -ne 0 ]; then
                      [ "$n" -gt 0 ] && echo $((n - 1)) > "$GETJSON_FAIL"
                      echo "rpc error: code = NotFound desc = no component json for git_sha" >&2
                      exit 1
                    fi
                  fi
                  if [ -n "$GETJSON_STALE" ] && [ -f "$GETJSON_STALE" ]; then
                    n=$(cat "$GETJSON_STALE")
                    if [ "$n" -ne 0 ]; then
                      [ "$n" -gt 0 ] && echo $((n - 1)) > "$GETJSON_STALE"
                      cat "$MOCK_DIR/no-push.json"
                      exit 0
                    fi
                  fi
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
        # A failed read must not fail the cron run (it re-runs next tick) — but
        # it is no longer reported as "no pushed container image", which is the
        # conflation ENG-1831 fixes. See ResolveRaceTest for the after-json leg,
        # where the same failure IS fatal because the wave is fire-once.
        self._stub("lunar", "#!/bin/sh\nexit 1\n")
        result, _ = self.run_script(dict(
            self.CRON_ENV,
            LUNAR_CONTAINER_SCAN_TEST_READ_BUDGET="2",
            LUNAR_CONTAINER_SCAN_TEST_BACKOFF_STEP="1",
        ))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Could not read Component JSON", result.stderr)
        self.assertNotIn("No pushed container image to scan", result.stderr)

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




class ResolveRaceTest(Base):
    """ENG-1831. The after-json wave is dispatched off the LIVE merged blob
    (hub.merged_collection_blobs) the moment the push record lands, but
    `lunar component get-json` reads through public.components[_latest] ->
    mat.component_json, a copy the Hub drains asynchronously. So the collector
    can be dispatched by a record it cannot yet read, and sha-pinning does not
    help — a pinned read goes through the same mat copy.

    Pre-fix the resolve was swallowed four ways on one line (`2>/dev/null`,
    `|| echo ""`, a silenced jq, then the shared `exit 0`), so the run recorded
    `finished, exit_code 0` and submitted an empty collection record. Because
    the wave is fire-once per (component, sha), that commit was never scanned.

    Measured on an internal Hub over 12 days (452 container-scan waves on one
    component): 66 shas had a push record that landed BEFORE the run started
    and still scanned nothing.
    """

    # Budgets/backoff shrunk via the script's test seam so the suite exercises
    # the real retry loop without sleeping for real.
    FAST = {
        "LUNAR_CONTAINER_SCAN_TEST_READ_BUDGET": "4",
        "LUNAR_CONTAINER_SCAN_TEST_RESOLVE_BUDGET": "4",
        "LUNAR_CONTAINER_SCAN_TEST_BACKOFF_STEP": "1",
    }

    def countdown(self, name, n):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as f:
            f.write(str(n))
        return path

    def test_stale_read_is_retried_until_the_push_record_appears(self):
        # THE REGRESSION. The first two reads succeed but predate the push
        # record (the mat copy has not drained), the third carries it. Pre-fix
        # the first read won and the commit was never scanned.
        env = dict(self.PR_ENV, **self.FAST,
                   GETJSON_STALE=self.countdown("stale", 2))
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(len(self.getjson_calls(log)), 3, msg=log)
        self.assertIn(f"Scanning image: {self.PR_IMAGE}", result.stderr)
        scan = self.collected(log, ".container_scan")
        self.assertIsNotNone(scan, msg=log)
        self.assertEqual(scan["image"], self.PR_IMAGE)

    def test_failed_read_is_retried_until_the_row_materializes(self):
        # The other shape: get-json returns NotFound until the sha's row drains.
        env = dict(self.PR_ENV, **self.FAST,
                   GETJSON_FAIL=self.countdown("fail", 2))
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(len(self.getjson_calls(log)), 3, msg=log)
        scan = self.collected(log, ".container_scan")
        self.assertEqual(scan["image"], self.PR_IMAGE)

    def test_happy_path_reads_once_and_never_sleeps(self):
        # The retry must cost nothing when the record is already readable —
        # otherwise every wave pays for the race. One call, no wait line.
        result, log = self.run_script(dict(self.PR_ENV, **self.FAST))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(len(self.getjson_calls(log)), 1, msg=log)
        self.assertNotIn("Waited", result.stderr)

    def test_persistent_read_failure_fails_the_after_json_run(self):
        # Fire-once: a swallowed read loses this commit's scan forever, so the
        # run has to show as failed rather than `finished, exit_code 0`.
        env = dict(self.PR_ENV, **self.FAST,
                   GETJSON_FAIL=self.countdown("fail", -1))
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertIn("Could not read Component JSON", result.stderr)
        self.assertIn("fire-once", result.stderr)
        # The CLI's own error reaches the run log instead of /dev/null.
        self.assertIn("get-json: rpc error", result.stderr)
        self.assertIsNone(self.collected(log, ".container_scan"))
        # ...and it is NOT reported as "nothing was pushed".
        self.assertNotIn("No pushed container image to scan", result.stderr)

    def test_persistent_no_push_ref_still_exits_zero_but_says_why(self):
        # A read that keeps succeeding with no pushed ref is ambiguous: the hook
        # fires on .containers.native.docker.cicd.cmds, which the docker
        # collector writes for ANY traced docker command, so "docker ran" is
        # enough to dispatch a wave (169 of those 452 waves never had a push
        # record at all). Failing here would redden a legitimate state — so it
        # waits out the resolve budget, then exits 0 saying the read SUCCEEDED.
        env = dict(self.PR_ENV, **self.FAST,
                   GETJSON_STALE=self.countdown("stale", -1))
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("No pushed container image to scan", result.stderr)
        self.assertIn("successfully", result.stderr)
        self.assertIn("Waited", result.stderr)
        self.assertGreater(len(self.getjson_calls(log)), 1, msg=log)
        self.assertIsNone(self.collected(log, ".container_scan"))

    def test_cron_does_not_wait_for_a_push_ref_to_appear(self):
        # The cron re-scan is not dispatched off a record, so it has no race to
        # lose to and runs again on the next tick. Waiting on every tick across
        # a fleet would be pure cost, so the resolve budget is zero there.
        env = dict(self.CRON_ENV, **self.FAST,
                   GETJSON_STALE=self.countdown("stale", -1))
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(len(self.getjson_calls(log)), 1, msg=log)
        self.assertNotIn("Waited", result.stderr)

    def test_cron_read_failure_skips_instead_of_failing(self):
        # Not fire-once, so a persistent read failure stays skip-safe — but the
        # message must no longer claim nothing was pushed.
        env = dict(self.CRON_ENV, **self.FAST,
                   GETJSON_FAIL=self.countdown("fail", -1))
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Could not read Component JSON", result.stderr)
        self.assertIn("next scheduled run", result.stderr)
        self.assertNotIn("No pushed container image to scan", result.stderr)
        self.assertIsNone(self.collected(log, ".container_scan"))

    def test_cli_error_is_surfaced_without_cobras_usage_block(self):
        # Dropping `2>/dev/null` is the point — the operator must see WHY the
        # read failed. But the real CLI prints ~18 lines of flag usage after
        # any error, so only the error itself is surfaced.
        self._stub("lunar", textwrap.dedent("""\
            #!/bin/sh
            if [ "$1" = "component" ] && [ "$2" = "get-json" ]; then
              printf 'GETJSON: %s\\n' "$*" >> "$CAPTURE"
              echo "Error: failed to fetch component JSON: rpc error: code = NotFound" >&2
              echo "Usage:" >&2
              echo "  lunar component get-json [flags]" >&2
              echo "      --git-sha string   The specific git SHA" >&2
              exit 1
            fi
            """))
        env = dict(self.CRON_ENV, **self.FAST)
        result, _ = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("get-json: Error: failed to fetch component JSON", result.stderr)
        self.assertNotIn("Usage:", result.stderr)
        self.assertNotIn("--git-sha string", result.stderr)

if __name__ == "__main__":
    unittest.main()
