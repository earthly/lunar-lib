#!/usr/bin/env python3
"""Tests for branch_protection.sh.

branch_protection.sh talks to the GitHub API via curl and writes results with
`lunar collect`. These tests run the real script with stubbed `curl`, `lunar`,
and `sleep` on PATH, then assert on its exit code and the `lunar collect` calls
it made.

The focus is the fail-open bug (ENG-1005): a transient GitHub API error
(rotated-token 401, 403/429 rate limit, 5xx, or a network failure) must NOT be
collapsed into a false `enabled=false / source=none`. On any such error the
script must exit non-zero so the run is marked errored and the prior good
`.vcs` data is retained. Only a classic-endpoint 404 ("Branch not protected")
is a legitimate signal to fall through to the rulesets path.
"""

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "branch_protection.sh")
)

# A representative classic branch-protection response (multi-line on purpose, to
# exercise the body/status-code splitting in gh_api).
CLASSIC_BODY = textwrap.dedent(
    """\
    {
      "required_pull_request_reviews": {
        "required_approving_review_count": 2,
        "require_code_owner_reviews": true,
        "dismiss_stale_reviews": true
      },
      "required_status_checks": { "strict": true, "contexts": ["ci/build"] },
      "allow_force_pushes": { "enabled": false },
      "allow_deletions": { "enabled": false },
      "required_linear_history": { "enabled": false },
      "required_signatures": { "enabled": true }
    }
    """
)

# A rulesets response with a pull_request rule (i.e. ruleset-based protection).
RULES_BODY = """[{"type":"pull_request","parameters":{"required_approving_review_count":1}},{"type":"non_fast_forward"}]"""

REPO_BODY = '{"default_branch":"main"}'


class BranchProtectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bp-test-")
        self.bin = os.path.join(self.tmp, "bin")
        self.mock = os.path.join(self.tmp, "mock")
        os.makedirs(self.bin)
        os.makedirs(self.mock)
        self.capture = os.path.join(self.tmp, "collect.log")
        self._write_stubs()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_stub(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, 0o755)

    def _write_stubs(self):
        # Fake curl: ignores every flag, keys off the URL (last arg), and emits
        # "<body><newline><status>" to mimic `curl -w '\\n%{http_code}'`. Reads a
        # per-endpoint status sequence + body from $MOCK_DIR so a single call
        # site can return different codes across retries. A status of NETFAIL
        # makes curl exit non-zero with no output (transport-level failure).
        self._write_stub(
            "curl",
            textwrap.dedent(
                """\
                #!/bin/sh
                url=""
                for a in "$@"; do url="$a"; done
                case "$url" in
                  */rules/branches/*) kind=rules ;;
                  */branches/*/protection) kind=classic ;;
                  *) kind=repo ;;
                esac
                ndir="$MOCK_DIR"
                n=$(cat "$ndir/$kind.n" 2>/dev/null || echo 0)
                n=$((n + 1)); echo "$n" > "$ndir/$kind.n"
                if [ -f "$ndir/$kind.codes" ]; then
                  code=$(sed -n "${n}p" "$ndir/$kind.codes")
                  [ -z "$code" ] && code=$(tail -n1 "$ndir/$kind.codes")
                else
                  code=200
                fi
                body=$(cat "$ndir/$kind.body" 2>/dev/null || echo '{}')
                if [ "$code" = "NETFAIL" ]; then exit 6; fi
                printf '%s\\n%s' "$body" "$code"
                """
            ),
        )
        # Fake lunar: append each `collect` invocation's args to the capture
        # log, draining stdin when the value is piped (trailing " -").
        self._write_stub(
            "lunar",
            textwrap.dedent(
                """\
                #!/bin/sh
                if [ "$1" = "collect" ]; then
                  args="$*"
                  case "$args" in
                    *" -") cat >/dev/null 2>&1 || true ;;
                  esac
                  printf '%s\\n' "$args" >> "$LUNAR_CAPTURE"
                fi
                exit 0
                """
            ),
        )
        # Fake sleep: no-op so retry tests run instantly.
        self._write_stub("sleep", "#!/bin/sh\nexit 0\n")

    def _set(self, kind, body=None, codes=None):
        if body is not None:
            with open(os.path.join(self.mock, f"{kind}.body"), "w") as f:
                f.write(body)
        if codes is not None:
            with open(os.path.join(self.mock, f"{kind}.codes"), "w") as f:
                f.write("\n".join(codes) + "\n")

    def _run(self):
        env = dict(os.environ)
        env["PATH"] = self.bin + os.pathsep + env.get("PATH", "")
        env["MOCK_DIR"] = self.mock
        env["LUNAR_CAPTURE"] = self.capture
        env["LUNAR_COMPONENT_ID"] = "github.com/acme/widget"
        env["LUNAR_SECRET_GH_TOKEN"] = "fake-token"
        proc = subprocess.run(
            ["bash", SCRIPT], env=env, capture_output=True, text=True
        )
        collected = ""
        if os.path.exists(self.capture):
            with open(self.capture) as f:
                collected = f.read()
        return proc.returncode, collected, proc.stderr

    # ---- genuine outcomes (must still work) ----

    def test_classic_protected_emits_enabled_true(self):
        self._set("repo", REPO_BODY)
        self._set("classic", CLASSIC_BODY, codes=["200"])
        rc, collected, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn(".vcs.branch_protection.enabled true", collected)
        self.assertIn('.vcs.branch_protection.source "classic"', collected)

    def test_ruleset_protected_emits_enabled_true(self):
        self._set("repo", REPO_BODY)
        self._set("classic", "{}", codes=["404"])
        self._set("rules", RULES_BODY, codes=["200"])
        rc, collected, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn(".vcs.branch_protection.enabled true", collected)
        self.assertIn('.vcs.branch_protection.source "ruleset"', collected)

    def test_genuinely_unprotected_emits_enabled_false(self):
        # classic 404 + empty rulesets array = truly unprotected. This is the
        # ONLY path allowed to emit enabled=false / source=none.
        self._set("repo", REPO_BODY)
        self._set("classic", "{}", codes=["404"])
        self._set("rules", "[]", codes=["200"])
        rc, collected, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn(".vcs.branch_protection.enabled false", collected)
        self.assertIn('.vcs.branch_protection.source "none"', collected)

    # ---- the fail-open bug: transient errors must error, never emit false ----

    def test_classic_401_aborts_without_emitting(self):
        # Rotated-token 401 on the classic endpoint (the ENG-1005 trigger).
        self._set("repo", REPO_BODY)
        self._set("classic", '{"message":"Bad credentials"}', codes=["401"])
        # Even if the rules endpoint would also fail, we must not get there.
        self._set("rules", '{"message":"Bad credentials"}', codes=["401"])
        rc, collected, _ = self._run()
        self.assertNotEqual(rc, 0)
        self.assertNotIn(".vcs.branch_protection.enabled", collected)

    def test_rules_401_after_classic_404_aborts_without_emitting(self):
        # classic legitimately 404s, but the rulesets call transiently 401s.
        self._set("repo", REPO_BODY)
        self._set("classic", "{}", codes=["404"])
        self._set("rules", '{"message":"Bad credentials"}', codes=["401"])
        rc, collected, _ = self._run()
        self.assertNotEqual(rc, 0)
        self.assertNotIn(".vcs.branch_protection.enabled", collected)

    def test_classic_403_rate_limit_aborts_without_emitting(self):
        self._set("repo", REPO_BODY)
        self._set("classic", '{"message":"API rate limit exceeded"}', codes=["403"])
        rc, collected, _ = self._run()
        self.assertNotEqual(rc, 0)
        self.assertNotIn(".vcs.branch_protection.enabled", collected)

    def test_repo_fetch_error_aborts_without_emitting(self):
        self._set("repo", '{"message":"Bad credentials"}', codes=["401"])
        rc, collected, _ = self._run()
        self.assertNotEqual(rc, 0)
        self.assertNotIn(".vcs.branch_protection.enabled", collected)

    def test_persistent_5xx_aborts_after_retries(self):
        self._set("repo", REPO_BODY)
        self._set("classic", "{}", codes=["503", "503", "503"])
        rc, collected, _ = self._run()
        self.assertNotEqual(rc, 0)
        self.assertNotIn(".vcs.branch_protection.enabled", collected)
        # 3 attempts (initial + 2 retries) should have been made.
        with open(os.path.join(self.mock, "classic.n")) as f:
            self.assertEqual(f.read().strip(), "3")

    def test_network_failure_aborts_without_emitting(self):
        self._set("repo", REPO_BODY)
        self._set("classic", "{}", codes=["NETFAIL"])
        rc, collected, _ = self._run()
        self.assertNotEqual(rc, 0)
        self.assertNotIn(".vcs.branch_protection.enabled", collected)

    # ---- retry recovers a transient blip ----

    def test_transient_5xx_then_success_recovers(self):
        self._set("repo", REPO_BODY)
        self._set("classic", CLASSIC_BODY, codes=["503", "503", "200"])
        rc, collected, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertIn(".vcs.branch_protection.enabled true", collected)
        self.assertIn('.vcs.branch_protection.source "classic"', collected)

    # ---- defensive: a 200 that isn't a JSON array on the rules endpoint ----

    def test_rules_non_array_200_aborts_without_emitting(self):
        self._set("repo", REPO_BODY)
        self._set("classic", "{}", codes=["404"])
        self._set("rules", '{"message":"unexpected"}', codes=["200"])
        rc, collected, _ = self._run()
        self.assertNotEqual(rc, 0)
        self.assertNotIn(".vcs.branch_protection.enabled", collected)


if __name__ == "__main__":
    unittest.main()
