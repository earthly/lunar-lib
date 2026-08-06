#!/usr/bin/env python3
"""Tests for the GitLab collector scripts.

Each script talks to the GitLab API via curl and writes results with
`lunar collect`. These tests run the real scripts with stubbed `curl` and
`lunar` on PATH, then assert on the `lunar collect` calls they made.

The curl stub returns canned JSON per endpoint (from $MOCK_DIR); the lunar stub
logs its args (and any piped stdin) to $CAPTURE.
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
        self.tmp = tempfile.mkdtemp(prefix="gl-test-")
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
        # curl stub: keys off the URL (last arg), returns a per-endpoint fixture
        # from $MOCK_DIR (empty defaults if the fixture is absent).
        self._stub(
            "curl",
            textwrap.dedent(
                """\
                #!/bin/sh
                url=""
                for a in "$@"; do url="$a"; done
                case "$url" in
                  */merge_requests/*)   cat "$MOCK_DIR/mr.json" ;;
                  */approval_rules)     cat "$MOCK_DIR/approval_rules.json" 2>/dev/null || echo '[]' ;;
                  */approvals)          cat "$MOCK_DIR/approvals.json" 2>/dev/null || echo '{}' ;;
                  */protected_branches) cat "$MOCK_DIR/protected.json" 2>/dev/null || echo '[]' ;;
                  */members/all*)       cat "$MOCK_DIR/members.json" 2>/dev/null || echo '[]' ;;
                  */projects/*)         cat "$MOCK_DIR/project.json" 2>/dev/null || echo '{}' ;;
                  *)                    echo '{}' ;;
                esac
                """
            ),
        )
        # lunar stub: log args, then log any piped stdin (labels/arrays).
        self._stub(
            "lunar",
            textwrap.dedent(
                """\
                #!/bin/sh
                printf 'ARGS: %s\\n' "$*" >> "$CAPTURE"
                data="$(cat)"
                if [ -n "$data" ]; then printf 'STDIN: %s\\n' "$data" >> "$CAPTURE"; fi
                """
            ),
        )

    def fixture(self, name, content):
        with open(os.path.join(self.mock, name), "w") as f:
            f.write(content)

    def run_script(self, script, env):
        full_env = {
            "PATH": self.bin + ":" + os.environ["PATH"],
            "MOCK_DIR": self.mock,
            "CAPTURE": self.capture,
        }
        full_env.update(env)
        result = subprocess.run(
            ["bash", os.path.join(COLLECTOR, script)],
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

    BASE_ENV = {
        "LUNAR_COMPONENT_ID": "gitlab.com/acme/backend",
        "LUNAR_SECRET_GL_TOKEN": "tok",
        "LUNAR_VAR_GITLAB_HOST": "gitlab.com",
    }


class MergeRequestTest(Base):
    MR = """
    {
      "iid": 42,
      "title": "[ENG-1] Add rate limiting",
      "description": "Implements a limiter.",
      "web_url": "https://gitlab.com/acme/backend/-/merge_requests/42",
      "source_branch": "eng-1-rate-limiting",
      "target_branch": "main",
      "author": {"username": "alice"},
      "labels": ["backend", "security"],
      "draft": false,
      "state": "opened"
    }
    """

    def test_happy_path(self):
        self.fixture("mr.json", self.MR)
        env = dict(self.BASE_ENV, LUNAR_COMPONENT_PR="42")
        result, log = self.run_script("merge_request.sh", env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('.vcs.pr.title [ENG-1] Add rate limiting', log)
        self.assertIn('.vcs.pr.source_branch eng-1-rate-limiting', log)
        self.assertIn('.vcs.pr.target_branch main', log)
        self.assertIn('.vcs.pr.author alice', log)
        # GitLab "opened" is normalized to the canonical "open".
        self.assertIn('.vcs.pr.state open', log)
        self.assertIn('.vcs.pr.number 42', log)
        self.assertIn('.vcs.pr.draft false', log)
        # labels are piped as JSON on stdin
        self.assertIn('"backend"', log)
        self.assertIn('"security"', log)

    def test_skips_without_pr_context(self):
        self.fixture("mr.json", self.MR)
        result, log = self.run_script("merge_request.sh", dict(self.BASE_ENV))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(log, "")

    def test_skips_wrong_host(self):
        self.fixture("mr.json", self.MR)
        env = dict(self.BASE_ENV, LUNAR_COMPONENT_ID="github.com/acme/backend",
                   LUNAR_COMPONENT_PR="42")
        result, log = self.run_script("merge_request.sh", env)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(log, "")

    def test_missing_token_errors(self):
        self.fixture("mr.json", self.MR)
        env = dict(self.BASE_ENV, LUNAR_COMPONENT_PR="42")
        del env["LUNAR_SECRET_GL_TOKEN"]
        result, _ = self.run_script("merge_request.sh", env)
        self.assertNotEqual(result.returncode, 0)


class RepositoryTest(Base):
    def _project(self, merge_method, squash_option="default_off"):
        return (
            '{"id":1,"default_branch":"main","visibility":"private",'
            '"topics":["backend"],"merge_method":"%s","squash_option":"%s"}'
            % (merge_method, squash_option)
        )

    def test_merge_method_merge(self):
        self.fixture("project.json", self._project("merge"))
        result, log = self.run_script("repository.sh", dict(self.BASE_ENV))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('.vcs.provider gitlab', log)
        self.assertIn('.vcs.merge_strategies.allow_merge_commit true', log)
        self.assertIn('.vcs.merge_strategies.allow_rebase_merge false', log)

    def test_merge_method_ff(self):
        self.fixture("project.json", self._project("ff"))
        result, log = self.run_script("repository.sh", dict(self.BASE_ENV))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('.vcs.merge_strategies.allow_merge_commit false', log)
        self.assertIn('.vcs.merge_strategies.allow_rebase_merge false', log)

    def test_merge_method_rebase(self):
        self.fixture("project.json", self._project("rebase_merge"))
        result, log = self.run_script("repository.sh", dict(self.BASE_ENV))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('.vcs.merge_strategies.allow_merge_commit false', log)
        self.assertIn('.vcs.merge_strategies.allow_rebase_merge true', log)

    def test_squash_never_disables(self):
        self.fixture("project.json", self._project("merge", "never"))
        result, log = self.run_script("repository.sh", dict(self.BASE_ENV))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('.vcs.merge_strategies.allow_squash_merge false', log)


class BranchProtectionTest(Base):
    PROJECT = '{"id":1,"default_branch":"main","only_allow_merge_if_pipeline_succeeds":true}'
    PROTECTED = ('[{"name":"main","allow_force_push":false,'
                 '"code_owner_approval_required":true,'
                 '"push_access_levels":[{"access_level":40}],'
                 '"merge_access_levels":[{"access_level":30}]}]')

    def test_protected_with_approval_rules(self):
        self.fixture("project.json", self.PROJECT)
        self.fixture("protected.json", self.PROTECTED)
        # Two rules apply to main (one all-branches, one main-scoped); a third is
        # scoped to a different branch and must be excluded. Sum = 2 + 1 = 3.
        self.fixture("approval_rules.json", (
            '[{"name":"All","approvals_required":2,"protected_branches":[]},'
            '{"name":"Sec","approvals_required":1,"protected_branches":[{"name":"main"}]},'
            '{"name":"Rel","approvals_required":5,"protected_branches":[{"name":"release"}]}]'
        ))
        result, log = self.run_script("branch_protection.sh", dict(self.BASE_ENV))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('.vcs.branch_protection.enabled true', log)
        self.assertIn('.vcs.branch_protection.source "gitlab"', log)
        self.assertIn('.vcs.branch_protection.required_approvals 3', log)
        self.assertIn('.vcs.branch_protection.require_codeowner_review true', log)
        self.assertIn('.vcs.branch_protection.require_status_checks true', log)
        self.assertIn('.vcs.branch_protection.restrictions.push_access_level maintainer', log)
        self.assertIn('.vcs.branch_protection.restrictions.merge_access_level developer', log)

    def test_falls_back_to_approvals_before_merge(self):
        # approval_rules 403s (unlicensed) -> stub returns [] -> fall back.
        self.fixture("project.json", self.PROJECT)
        self.fixture("protected.json", self.PROTECTED)
        self.fixture("approvals.json", '{"approvals_before_merge":2}')
        result, log = self.run_script("branch_protection.sh", dict(self.BASE_ENV))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('.vcs.branch_protection.required_approvals 2', log)

    def test_unprotected_default_branch(self):
        self.fixture("project.json", self.PROJECT)
        self.fixture("protected.json", '[]')
        result, log = self.run_script("branch_protection.sh", dict(self.BASE_ENV))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('.vcs.branch_protection.enabled false', log)
        self.assertIn('.vcs.branch_protection.source "gitlab"', log)


if __name__ == "__main__":
    unittest.main()
