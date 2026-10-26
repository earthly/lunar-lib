"""Drives lunar-github-token with a stub `lunar` CLI on PATH."""
import json
import os
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "lunar-github-token")

APP_TOKEN = "ghs_app_token_from_hub"
PAT = "ghp_stored_secret"
GHES_PAT = "ghp_enterprise_secret"

# The stub records its argv and answers per STUB_MODE.
STUB = """#!/bin/bash
printf '%s\\n' "$@" > "$STUB_ARGS"
case "$STUB_MODE" in
  ok) printf '%s' '{"token":"ghs_app_token_from_hub","installation_id":42,"expires_at":"2026-10-26T19:00:00Z"}' ;;
  notfound) echo 'Error: rpc error: code = NotFound desc = no App is named "lunar-lib"' >&2; exit 1 ;;
  notinstalled) echo 'Error: rpc error: code = FailedPrecondition desc = GitHub App lunar-lib is not installed on acme' >&2; exit 1 ;;
  oldcli) echo 'Usage:'; echo '  lunar [command]' ;;
esac
"""


class LunarGithubTokenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = os.path.join(self.tmp.name, "bin")
        os.mkdir(self.bin)
        self.args_file = os.path.join(self.tmp.name, "args")
        stub = os.path.join(self.bin, "lunar")
        with open(stub, "w") as f:
            f.write(STUB)
        os.chmod(stub, stat.S_IRWXU)

    def tearDown(self):
        self.tmp.cleanup()

    def run_helper(self, mode="ok", env=None, args=(), stub=True):
        path = self.bin if stub else ""
        # Keep bash, jq, grep, sed and cut reachable without the real lunar.
        path += ":/usr/bin:/bin"
        e = {"PATH": path, "STUB_MODE": mode, "STUB_ARGS": self.args_file,
             "LUNAR_SECRET_GH_TOKEN": PAT}
        e.update(env or {})
        e = {k: v for k, v in e.items() if v is not None}
        p = subprocess.run(["bash", SCRIPT, *args], env=e, capture_output=True, text=True)
        return p.returncode, p.stdout.strip(), p.stderr

    def lunar_args(self):
        with open(self.args_file) as f:
            return f.read().split("\n")[:-1]

    def test_app_token(self):
        code, out, err = self.run_helper("ok")
        self.assertEqual((code, out), (0, APP_TOKEN))
        self.assertIn("GitHub auth: GitHub App lunar-lib (installation 42)", err)
        self.assertEqual(self.lunar_args(), ["github-app", "get-token", "lunar-lib", "--output-json"])

    def test_falls_back_to_secret_when_app_missing(self):
        code, out, err = self.run_helper("notfound")
        self.assertEqual((code, out), (0, PAT))
        self.assertIn('the GH_TOKEN secret, because GitHub App lunar-lib can\'t mint a token: no App is named "lunar-lib"', err)

    def test_falls_back_when_not_installed_on_owner(self):
        code, out, err = self.run_helper("notinstalled")
        self.assertEqual((code, out), (0, PAT))
        self.assertIn("is not installed on acme", err)

    def test_nothing_when_no_app_and_no_secret(self):
        code, out, err = self.run_helper("notfound", env={"LUNAR_SECRET_GH_TOKEN": None})
        self.assertEqual((code, out), (0, ""))
        self.assertIn("none, because", err)
        self.assertIn("the GH_TOKEN secret is not set", err)

    def test_app_only_fails_instead_of_falling_back(self):
        code, out, err = self.run_helper("notfound", env={"LUNAR_VAR_GITHUB_APP_ONLY": "true"})
        self.assertEqual((code, out), (1, ""))
        self.assertIn("github_app_only is set", err)

    def test_app_only_still_uses_the_app(self):
        code, out, _ = self.run_helper("ok", env={"LUNAR_VAR_GITHUB_APP_ONLY": "true"})
        self.assertEqual((code, out), (0, APP_TOKEN))

    def test_empty_github_app_skips_the_app(self):
        code, out, err = self.run_helper("ok", env={"LUNAR_VAR_GITHUB_APP": ""})
        self.assertEqual((code, out), (0, PAT))
        self.assertIn("the github_app input is empty", err)
        self.assertFalse(os.path.exists(self.args_file), "lunar should not be called")

    def test_custom_app_owner_and_host(self):
        code, out, _ = self.run_helper(
            "ok", env={"LUNAR_VAR_GITHUB_APP": "acme-reader"},
            args=["--owner", "acme", "--host", "ghes.example.com"])
        self.assertEqual((code, out), (0, APP_TOKEN))
        self.assertEqual(self.lunar_args(), ["github-app", "get-token", "acme-reader", "--output-json",
                                             "--owner", "acme", "--host", "ghes.example.com"])

    def test_fallback_env(self):
        code, out, err = self.run_helper(
            "notfound", env={"LUNAR_SECRET_GH_ENTERPRISE_TOKEN": GHES_PAT},
            args=["--fallback-env", "LUNAR_SECRET_GH_ENTERPRISE_TOKEN"])
        self.assertEqual((code, out), (0, GHES_PAT))
        self.assertIn("the GH_ENTERPRISE_TOKEN secret, because", err)

    def test_cli_without_github_app_falls_back(self):
        # An old CLI prints usage and exits 0 for an unknown command.
        code, out, err = self.run_helper("oldcli")
        self.assertEqual((code, out), (0, PAT))
        self.assertIn("returned no token", err)

    def test_missing_cli_falls_back(self):
        code, out, err = self.run_helper("ok", stub=False)
        self.assertEqual((code, out), (0, PAT))
        self.assertIn("the lunar CLI is missing", err)

    def test_tokens_never_logged(self):
        for mode in ("ok", "notfound", "notinstalled", "oldcli"):
            _, _, err = self.run_helper(mode)
            self.assertNotIn(APP_TOKEN, err, mode)
            self.assertNotIn(PAT, err, mode)

    def test_unknown_argument(self):
        code, _, err = self.run_helper("ok", args=["--bogus"])
        self.assertEqual(code, 2)
        self.assertIn("unknown argument", err)


if __name__ == "__main__":
    unittest.main()
