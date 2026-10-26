"""Runs the GitHub plugins' real scripts against a stub `lunar` that can or
can't mint a GitHub App token, and a stub `curl` that records the token each
GitHub request carries."""
import json
import os
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
# The repo root in a checkout; the working directory when Earthly copies the
# plugins next to this file.
ROOT = next(p for p in (os.path.dirname(HERE), HERE)
            if os.path.isdir(os.path.join(p, "collectors")))

APP_TOKEN = "ghs_app_token_from_hub"
PAT = "ghp_stored_secret"

SCRIPTS = [
    "collectors/github/repository.sh",
    "collectors/github/access_permissions.sh",
    "collectors/github/branch_protection.sh",
    "collectors/github/pull_request.sh",
    "collectors/claude/code-reviewer.sh",
    "collectors/coderabbit/code-reviewer.sh",
    "collectors/codeql/github-app.sh",
    "collectors/semgrep/github-app.sh",
    "collectors/snyk/github-app.sh",
    "collectors/sonarqube/github-app.sh",
    "collectors/jira/ticket.sh",
    "catalogers/backstage-catalog-info/main.sh",
]

# get-token prints the token per STUB_MODE; everything else (collect, catalog)
# swallows its input.
LUNAR_STUB = """#!/bin/bash
if [ "$1 $2" = "github-app get-token" ]; then
  printf '%s\\n' "$@" > "$LUNAR_ARGS"
  case "$STUB_MODE" in
    ok) echo "ghs_app_token_from_hub" ;;
    empty) ;;
    *) echo 'Error: rpc error: code = NotFound desc = no App is named "lunar-lib"' >&2; exit 1 ;;
  esac
  exit 0
fi
cat >/dev/null 2>&1 || true
"""

CURL_STUB = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
url = next((a for a in reversed(args) if a.startswith("http")), "")
auth = [args[i + 1] for i, a in enumerate(args[:-1])
        if a == "-H" and args[i + 1].lower().startswith("authorization:")]
with open(os.environ["CURL_LOG"], "a") as f:
    f.write(json.dumps({"url": url, "token": auth[0].split()[-1] if auth else None}) + "\\n")
if "/check-runs" in url:
    body = '{"total_count":0,"check_runs":[]}'
elif url.endswith("/status"):
    body = '{"state":"success","statuses":[]}'
elif "/teams" in url or "/collaborators" in url or url.endswith("/commits") or "/reviews" in url:
    body = "[]"
elif "/contents/" in url:
    body = '{"message":"Not Found"}'
else:
    body = '{"default_branch":"main","name":"widget","full_name":"acme/widget","title":"ABC-1 widget"}'
code = "404" if "/protection" in url or "/contents/" in url else "200"
if "-o" in args:
    open(args[args.index("-o") + 1], "w").write(body)
    body = ""
if "-w" in args:
    body += ("\\n" if body else "") + code
sys.stdout.write(body)
"""

# Records the tokens gh would authenticate with, then lists no repos.
GH_STUB = """#!/bin/bash
echo "${GH_TOKEN:-}|${GH_ENTERPRISE_TOKEN:-}" >> "$GH_LOG"
echo "[]"
"""


class GithubAppAuthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = os.path.join(self.tmp.name, "bin")
        os.mkdir(self.bin)
        self.curl_log = os.path.join(self.tmp.name, "curl.jsonl")
        self.lunar_args = os.path.join(self.tmp.name, "lunar-args")
        self.gh_log = os.path.join(self.tmp.name, "gh.log")
        for name, body in (("lunar", LUNAR_STUB), ("curl", CURL_STUB), ("gh", GH_STUB),
                           ("sleep", "#!/bin/sh\n")):
            path = os.path.join(self.bin, name)
            with open(path, "w") as f:
                f.write(body)
            os.chmod(path, stat.S_IRWXU)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, script, mode, **env):
        for log in (self.curl_log, self.lunar_args, self.gh_log):
            if os.path.exists(log):
                os.remove(log)
        e = {"PATH": self.bin + ":/usr/local/bin:/usr/bin:/bin", "STUB_MODE": mode,
             "CURL_LOG": self.curl_log, "LUNAR_ARGS": self.lunar_args, "GH_LOG": self.gh_log,
             "LUNAR_SECRET_GH_TOKEN": PAT,
             "LUNAR_COMPONENT_ID": "github.com/acme/widget",
             "LUNAR_COMPONENT_GIT_SHA": "0123456789abcdef0123456789abcdef01234567",
             "LUNAR_COMPONENT_PR": "7"}
        e.update(env)
        p = subprocess.run(["bash", os.path.join(ROOT, script)], env=e,
                           capture_output=True, text=True, timeout=120)
        reqs = []
        if os.path.exists(self.curl_log):
            with open(self.curl_log) as f:
                reqs = [json.loads(line) for line in f if "api.github.com" in line]
        return p.returncode, reqs, p.stderr

    def test_app_token_when_the_app_mints(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                _, reqs, err = self.run_script(script, "ok")
                self.assertTrue(reqs, f"no GitHub request made: {err[-500:]}")
                self.assertEqual({r["token"] for r in reqs}, {APP_TOKEN})
                self.assertIn("GitHub auth: GitHub App lunar-lib", err)

    def test_secret_when_the_app_cannot_mint(self):
        for mode in ("notfound", "empty"):
            for script in SCRIPTS:
                with self.subTest(script=script, mode=mode):
                    _, reqs, err = self.run_script(script, mode)
                    self.assertTrue(reqs, f"no GitHub request made: {err[-500:]}")
                    self.assertEqual({r["token"] for r in reqs}, {PAT})
                    self.assertIn("GitHub auth: GH_TOKEN secret", err)

    def test_app_only_fails_before_any_request(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                code, reqs, err = self.run_script(script, "notfound", LUNAR_VAR_GITHUB_APP_ONLY="true")
                self.assertEqual(code, 1, err[-500:])
                self.assertEqual(reqs, [])
                self.assertIn("github_app_only is set", err)

    def test_custom_app_name(self):
        self.run_script(SCRIPTS[0], "ok", LUNAR_VAR_GITHUB_APP="acme-reader")
        with open(self.lunar_args) as f:
            self.assertEqual(f.read().split("\n")[:3], ["github-app", "get-token", "acme-reader"])

    def test_github_org_mints_for_its_org_and_host(self):
        script = "catalogers/github-org/main.sh"
        for host, var in (("github.com", "GH_TOKEN"), ("ghes.example.com", "GH_ENTERPRISE_TOKEN")):
            with self.subTest(host=host):
                self.run_script(script, "ok", LUNAR_VAR_ORG_NAME="acme", LUNAR_VAR_GITHUB_HOST=host)
                with open(self.lunar_args) as f:
                    args = f.read().split("\n")
                self.assertEqual(args[args.index("--owner") + 1], "acme")
                self.assertEqual(args[args.index("--host") + 1], host)
                with open(self.gh_log) as f:
                    gh_token, gh_enterprise_token = f.readline().strip().split("|")
                self.assertEqual(gh_token if var == "GH_TOKEN" else gh_enterprise_token, APP_TOKEN)

    def test_github_org_falls_back_to_the_secret(self):
        self.run_script("catalogers/github-org/main.sh", "notfound", LUNAR_VAR_ORG_NAME="acme")
        with open(self.gh_log) as f:
            self.assertEqual(f.readline().strip().split("|")[0], PAT)


if __name__ == "__main__":
    unittest.main()
