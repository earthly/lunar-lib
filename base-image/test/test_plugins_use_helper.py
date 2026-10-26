"""Runs real plugin scripts with lunar-github-token on PATH, a stub `lunar`
that can or can't mint an App token, and a stub `curl` that records the token
each GitHub request carries."""
import json
import os
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HELPER = os.path.join(HERE, "..", "lunar-github-token")
# The repo's collectors/ in a checkout, or copied next to the test by Earthly.
ROOT = next(p for p in (os.path.join(HERE, "..", ".."), HERE)
            if os.path.isdir(os.path.join(p, "collectors")))

APP_TOKEN = "ghs_app_token_from_hub"
PAT = "ghp_stored_secret"

SCRIPTS = [
    "collectors/github/repository.sh",
    "collectors/github/access_permissions.sh",
    "collectors/github/branch_protection.sh",
    "collectors/claude/code-reviewer.sh",
    "collectors/coderabbit/code-reviewer.sh",
    "collectors/codeql/github-app.sh",
    "collectors/semgrep/github-app.sh",
    "collectors/snyk/github-app.sh",
]

LUNAR_STUB = """#!/bin/bash
if [ "$1 $2" = "github-app get-token" ]; then
  case "$STUB_MODE" in
    ok) printf '%s' '{"token":"ghs_app_token_from_hub","installation_id":42}' ;;
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
elif "/teams" in url or "/collaborators" in url:
    body = "[]"
else:
    body = '{"default_branch":"main","name":"widget","full_name":"acme/widget"}'
code = "404" if "/protection" in url else "200"
if "-o" in args:
    open(args[args.index("-o") + 1], "w").write(body)
    body = ""
fmt = args[args.index("-w") + 1] if "-w" in args else None
sys.stdout.write(body + ((("\\n" if body else "") + code) if fmt else ""))
"""


class PluginsUseHelperTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = os.path.join(self.tmp.name, "bin")
        os.mkdir(self.bin)
        self.log = os.path.join(self.tmp.name, "curl.jsonl")
        for name, body in (("lunar", LUNAR_STUB), ("curl", CURL_STUB), ("sleep", "#!/bin/sh\n")):
            self._write_exec(name, body)
        with open(HELPER) as f:
            self._write_exec("lunar-github-token", f.read())

    def tearDown(self):
        self.tmp.cleanup()

    def _write_exec(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, stat.S_IRWXU)

    def run_script(self, script, mode, **env):
        if os.path.exists(self.log):
            os.remove(self.log)
        e = {"PATH": self.bin + ":/usr/local/bin:/usr/bin:/bin", "STUB_MODE": mode,
             "CURL_LOG": self.log, "LUNAR_SECRET_GH_TOKEN": PAT,
             "LUNAR_COMPONENT_ID": "github.com/acme/widget",
             "LUNAR_COMPONENT_GIT_SHA": "0123456789abcdef0123456789abcdef01234567"}
        e.update(env)
        p = subprocess.run(["bash", os.path.join(ROOT, script)], env=e,
                           capture_output=True, text=True, timeout=120)
        requests = []
        if os.path.exists(self.log):
            with open(self.log) as f:
                requests = [json.loads(line) for line in f]
        github = [r for r in requests if "api.github.com" in r["url"]]
        return p.returncode, github, p.stderr

    def test_app_token_when_the_app_mints(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                _, reqs, err = self.run_script(script, "ok")
                self.assertTrue(reqs, f"no GitHub request made: {err[-500:]}")
                self.assertEqual({r["token"] for r in reqs}, {APP_TOKEN})
                self.assertIn("GitHub auth: GitHub App lunar-lib (installation 42)", err)

    def test_secret_when_the_app_cannot_mint(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                _, reqs, err = self.run_script(script, "notfound")
                self.assertTrue(reqs, f"no GitHub request made: {err[-500:]}")
                self.assertEqual({r["token"] for r in reqs}, {PAT})
                self.assertIn("GitHub auth: the GH_TOKEN secret, because", err)

    def test_app_only_fails_before_any_request(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                code, reqs, _ = self.run_script(script, "notfound", LUNAR_VAR_GITHUB_APP_ONLY="true")
                self.assertEqual(code, 1)
                self.assertEqual(reqs, [])


if __name__ == "__main__":
    unittest.main()
