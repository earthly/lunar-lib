#!/usr/bin/env python3
"""Tests for the jira ticket-from-json (after-json) collector.

ticket_from_json.sh reads the PR's title/description from the *PR-scoped*
Component JSON via `lunar component get-json`, then resolves the ticket with the
shared helpers. The regression these tests lock in: the script must pass
`--pr "$LUNAR_COMPONENT_PR"` to get-json — without it, get-json returns the
main-branch JSON (which has no `.vcs.pr`) and the ticket is never resolved.

The `lunar` stub returns PR-scoped JSON only when `--pr` is present (mirroring
the Hub) and logs its `collect` calls to $CAPTURE; the real script runs as a
subprocess. No Jira is configured, so resolution takes the best candidate
unchecked — enough to prove the PR title was read.
"""

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
        self.tmp = tempfile.mkdtemp(prefix="jira-test-")
        self.bin = os.path.join(self.tmp, "bin")
        self.mock = os.path.join(self.tmp, "mock")
        os.makedirs(self.bin)
        os.makedirs(self.mock)
        self.capture = os.path.join(self.tmp, "collect.log")
        self._write_stubs()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stub(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, 0o755)

    def _write_stubs(self):
        # lunar stub: `component get-json` returns the PR-scoped fixture only
        # when --pr is passed, else the main-branch fixture (no .vcs.pr) —
        # exactly the distinction the real Hub makes. Everything else (collect)
        # is logged to $CAPTURE: args, then any piped stdin.
        self._stub(
            "lunar",
            textwrap.dedent(
                """\
                #!/bin/sh
                printf 'ARGS: %s\\n' "$*" >> "$CAPTURE"
                if [ "$1" = "component" ] && [ "$2" = "get-json" ]; then
                  # Test seams, both off by default. Each names a countdown file
                  # holding the number of remaining calls that should misbehave;
                  # -1 means forever. This models the Hub's mat lag: the read
                  # either fails outright or succeeds while still missing the
                  # .vcs.pr.title that dispatched the wave.
                  if [ -n "$GETJSON_FAIL" ] && [ -f "$GETJSON_FAIL" ]; then
                    n=$(cat "$GETJSON_FAIL")
                    if [ "$n" -ne 0 ]; then
                      [ "$n" -gt 0 ] && echo $((n - 1)) > "$GETJSON_FAIL"
                      echo "rpc error: code = NotFound desc = failed to load component" >&2
                      echo "Usage:" >&2
                      echo "  lunar component get-json [flags]" >&2
                      exit 1
                    fi
                  fi
                  if [ -n "$GETJSON_STALE" ] && [ -f "$GETJSON_STALE" ]; then
                    n=$(cat "$GETJSON_STALE")
                    if [ "$n" -ne 0 ]; then
                      [ "$n" -gt 0 ] && echo $((n - 1)) > "$GETJSON_STALE"
                      cat "$MOCK_DIR/main.json"
                      exit 0
                    fi
                  fi
                  for a in "$@"; do
                    if [ "$a" = "--pr" ]; then cat "$MOCK_DIR/pr.json"; exit 0; fi
                  done
                  cat "$MOCK_DIR/main.json"
                  exit 0
                fi
                data="$(cat)"
                if [ -n "$data" ]; then printf 'STDIN: %s\\n' "$data" >> "$CAPTURE"; fi
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
            ["bash", os.path.join(COLLECTOR, "ticket_from_json.sh")],
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

    # PR-scoped JSON carries .vcs.pr.* (written by the github/gitlab producer);
    # the main-branch JSON does not.
    PR_JSON = '{"vcs":{"pr":{"title":"[ABC-123] Add healthz","description":"Ticket: ABC-123"}}}'
    MAIN_JSON = '{"vcs":{}}'

    BASE_ENV = {"LUNAR_COMPONENT_ID": "github.com/acme/backend"}


class TicketFromJsonTest(Base):
    def test_resolves_ticket_from_pr_scoped_json(self):
        # In PR context the collector must pass --pr so get-json returns the PR
        # JSON; the ticket is then resolved from the title. This fails if the
        # script fetches get-json without --pr (the pre-fix regression).
        self.fixture("pr.json", self.PR_JSON)
        self.fixture("main.json", self.MAIN_JSON)
        result, log = self.run_script(dict(self.BASE_ENV, LUNAR_COMPONENT_PR="8"))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("--pr 8", log)  # get-json was PR-scoped
        self.assertIn(".vcs.pr.ticket.id", log)  # ticket was resolved + collected
        self.assertIn("ABC-123", log)

    def test_skips_cleanly_without_pr_context(self):
        # No LUNAR_COMPONENT_PR (not a PR run): no --pr, get-json returns the
        # main-branch JSON with no .vcs.pr, and the collector skips without
        # writing a ticket. Must still exit 0 so it doesn't fail the run.
        self.fixture("pr.json", self.PR_JSON)
        self.fixture("main.json", self.MAIN_JSON)
        result, log = self.run_script(dict(self.BASE_ENV))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn(".vcs.pr.ticket.id", log)


class ReadRaceTest(Base):
    """ENG-1831. The after-json wave is dispatched off the LIVE merged blob the
    instant .vcs.pr.title lands, but `lunar component get-json` reads it back
    through a copy the Hub drains asynchronously — so this collector can be
    dispatched by a record it cannot yet read.

    The hook's path IS this collector's input (`after-json` on .vcs.pr.title),
    and the Hub fires only collectors whose path is present in that live blob.
    So in PR context a missing title cannot mean the PR has no title; it means
    the read is stale. Pre-fix `2>/dev/null || echo ""` plus the shared skip
    turned that into `exit 0`, and because the wave is fire-once per
    (component, sha), the PR's ticket was lost for good.
    """

    FAST = {
        "LUNAR_JIRA_TEST_READ_BUDGET": "4",
        "LUNAR_JIRA_TEST_BACKOFF_STEP": "1",
    }

    def setUp(self):
        super().setUp()
        self.fixture("pr.json", self.PR_JSON)
        self.fixture("main.json", self.MAIN_JSON)

    def countdown(self, name, n):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as f:
            f.write(str(n))
        return path

    def getjson_calls(self, log):
        return [ln for ln in log.splitlines() if "component get-json" in ln]

    def test_stale_read_is_retried_until_the_title_appears(self):
        # THE REGRESSION: the first two reads land before .vcs.pr.title has
        # drained, the third carries it. Pre-fix the first read won and the
        # ticket was never recorded.
        env = dict(self.BASE_ENV, LUNAR_COMPONENT_PR="8", **self.FAST,
                   GETJSON_STALE=self.countdown("stale", 2))
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(len(self.getjson_calls(log)), 3, msg=log)
        self.assertIn(".vcs.pr.ticket.id", log)
        self.assertIn("ABC-123", log)

    def test_happy_path_reads_once_and_never_sleeps(self):
        env = dict(self.BASE_ENV, LUNAR_COMPONENT_PR="8", **self.FAST)
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(len(self.getjson_calls(log)), 1, msg=log)
        self.assertNotIn("Waited", result.stderr)

    def test_persistent_stale_read_fails_the_run_in_pr_context(self):
        env = dict(self.BASE_ENV, LUNAR_COMPONENT_PR="8", **self.FAST,
                   GETJSON_STALE=self.countdown("stale", -1))
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertIn("fire-once", result.stderr)
        self.assertNotIn(".vcs.pr.ticket.id", log)

    def test_failed_read_surfaces_the_error_without_the_usage_block(self):
        env = dict(self.BASE_ENV, LUNAR_COMPONENT_PR="8", **self.FAST,
                   GETJSON_FAIL=self.countdown("fail", -1))
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertIn("get-json: rpc error", result.stderr)
        self.assertNotIn("Usage:", result.stderr)
        self.assertNotIn(".vcs.pr.ticket.id", log)

    def test_no_pr_context_still_skips_without_waiting(self):
        # A branch push has no .vcs.pr.title for the hook to match, so the wave
        # never fires there — that path is only reached by a manual/dev run,
        # where an absent title is genuine. Unchanged: one read, skip, exit 0.
        env = dict(self.BASE_ENV, **self.FAST,
                   GETJSON_STALE=self.countdown("stale", -1))
        result, log = self.run_script(env)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(len(self.getjson_calls(log)), 1, msg=log)
        self.assertNotIn("Waited", result.stderr)
        self.assertNotIn(".vcs.pr.ticket.id", log)


if __name__ == "__main__":
    unittest.main()
