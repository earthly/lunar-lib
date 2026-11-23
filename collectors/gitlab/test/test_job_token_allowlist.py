#!/usr/bin/env python3
"""Tests for job_token_allowlist.sh.

The script runs unmodified with real curl against a local HTTPS mock of the
GitLab API, so status codes, headers, retries and URL encoding go through the
same code paths as in production. A curlrc (via CURL_HOME) points
gitlab.example.com at the mock and trusts its throwaway certificate. Only
`lunar` (records each collect call) and `sleep` (records the delay, returns at
once) are stubbed.
"""

import http.server
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import textwrap
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "job_token_allowlist.sh")

HOST = "gitlab.example.com"
TOKEN = "glpat-test-only-not-a-real-token"
SCOPE_TOKEN = "glpat-test-only-maintainer-token"
SCOPE = "/api/v4/projects/42/job_token_scope"
ALLOWLIST = SCOPE + "/allowlist"
GROUPS = SCOPE + "/groups_allowlist"
ISO_UTC = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

LUNAR_STUB = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    data = sys.stdin.read() if args[-1:] == ["-"] else ""
    with open(os.environ["LUNAR_CAPTURE"], "a") as f:
        f.write(json.dumps({"args": args, "stdin": data}) + "\\n")
    """
)

SLEEP_STUB = textwrap.dedent(
    """\
    #!/bin/sh
    echo "$1" >> "$SLEEP_CAPTURE"
    """
)


def ok(body):
    return (200, body, {})


def project(pid, path):
    return {"id": pid, "path_with_namespace": path, "name": path.rsplit("/", 1)[-1]}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        srv = self.server
        srv.requests.append({"path": self.path, "token": self.headers.get("PRIVATE-TOKEN")})
        key = self.path if self.path in srv.routes else self.path.split("?", 1)[0]
        if key in srv.routes:
            served = srv.served.get(key, 0)
            srv.served[key] = served + 1
            responses = srv.routes[key]
            status, body, headers = responses[min(served, len(responses) - 1)]
        else:
            status, body, headers = 404, {"error": "404 Not Found"}, {}
        data = (body if isinstance(body, str) else json.dumps(body)).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class JobTokenAllowlistTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.certdir = tempfile.mkdtemp(prefix="gl-jt-cert-")
        cls.cert = os.path.join(cls.certdir, "cert.pem")
        key = os.path.join(cls.certdir, "key.pem")
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
             "-nodes", "-keyout", key, "-out", cls.cert, "-days", "1", "-subj", f"/CN={HOST}",
             "-addext", f"subjectAltName=DNS:{HOST}"],
            check=True, capture_output=True,
        )
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.server.daemon_threads = True
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cls.cert, key)
        cls.server.socket = ctx.wrap_socket(cls.server.socket, server_side=True)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.certdir, ignore_errors=True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gl-jt-")
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        for name, body in (("lunar", LUNAR_STUB), ("sleep", SLEEP_STUB)):
            path = os.path.join(self.bin, name)
            with open(path, "w") as f:
                f.write(body)
            os.chmod(path, 0o755)
        self.capture = os.path.join(self.tmp, "collect.jsonl")
        self.sleeps_file = os.path.join(self.tmp, "sleeps")
        self.reset()

    def reset(self):
        """Fresh mock routes, request log and captures (also between subtests)."""
        self.server.routes = {}
        self.server.served = {}
        self.server.requests = []
        for path in (self.capture, self.sleeps_file):
            if os.path.exists(path):
                os.remove(path)
        self.point_curl_at(self.port)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def point_curl_at(self, port):
        with open(os.path.join(self.tmp, ".curlrc"), "w") as f:
            f.write(f'connect-to = "{HOST}:443:127.0.0.1:{port}"\ncacert = "{self.cert}"\n')

    def route(self, path, *responses):
        self.server.routes[path] = list(responses)

    def run_script(self, meta='{"project_id": "42"}', **overrides):
        env = {
            "PATH": self.bin + ":" + os.environ["PATH"],
            "HOME": self.tmp,
            "CURL_HOME": self.tmp,
            "LUNAR_CAPTURE": self.capture,
            "SLEEP_CAPTURE": self.sleeps_file,
            "LUNAR_COMPONENT_ID": f"{HOST}/acme/platform/backend",
            "LUNAR_VAR_GITLAB_HOST": HOST,
            "LUNAR_SECRET_GL_TOKEN": TOKEN,
        }
        if meta is not None:
            env["LUNAR_COMPONENT_META"] = meta
        env.update(overrides)
        env = {k: v for k, v in env.items() if v is not None}
        result = subprocess.run(["bash", SCRIPT], env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=120)
        for token in (TOKEN, SCOPE_TOKEN):
            self.assertNotIn(token, result.stdout + result.stderr, "a token leaked into the output")
        return result

    def collected(self):
        """Every lunar collect call, as (args, parsed stdin)."""
        if not os.path.exists(self.capture):
            return []
        with open(self.capture) as f:
            calls = [json.loads(line) for line in f]
        return [(c["args"], json.loads(c["stdin"]) if c["stdin"] else None) for c in calls]

    def written(self):
        """The one .vcs.job_token_allowlist object the run wrote."""
        calls = self.collected()
        self.assertEqual(len(calls), 1, calls)
        args, value = calls[0]
        self.assertEqual(args, ["collect", "-j", ".vcs.job_token_allowlist", "-"])
        self.assertRegex(value.pop("checked_at"), ISO_UTC)
        return value

    def paths(self):
        return [r["path"] for r in self.server.requests]

    def sleeps(self):
        if not os.path.exists(self.sleeps_file):
            return []
        with open(self.sleeps_file) as f:
            return [line.strip() for line in f]

    # --- known states -------------------------------------------------------

    def test_enabled_counts_other_projects_and_groups(self):
        self.route(SCOPE, ok({"inbound_enabled": True, "outbound_enabled": False}))
        self.route(ALLOWLIST, ok([project(42, "acme/platform/backend"),
                                  project(7, "acme/platform/deployer"),
                                  project(8, "acme/tools/release")]))
        self.route(GROUPS, ok([{"id": 100, "full_path": "acme/infra"}]))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), {"enabled": True, "projects": 2, "groups": 1})
        self.assertEqual(self.paths(), [SCOPE,
                                        ALLOWLIST + "?per_page=100&page=1",
                                        GROUPS + "?per_page=100&page=1"])
        self.assertTrue(all(r["token"] == TOKEN for r in self.server.requests))

    def test_enabled_with_only_the_project_itself(self):
        self.route(SCOPE, ok({"inbound_enabled": True, "outbound_enabled": False}))
        self.route(ALLOWLIST, ok([project(42, "acme/platform/backend")]))
        self.route(GROUPS, ok([]))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), {"enabled": True, "projects": 0, "groups": 0})

    def test_disabled_reads_no_lists(self):
        # Entries left over from before the toggle went off don't count: GitLab ignores them.
        self.route(SCOPE, ok({"inbound_enabled": False, "outbound_enabled": True}))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), {"enabled": False})
        self.assertEqual(self.paths(), [SCOPE])

    def test_counts_every_page(self):
        first = [project(42, "acme/platform/backend")] + [project(1000 + i, f"acme/p{i}") for i in range(99)]
        self.route(SCOPE, ok({"inbound_enabled": True}))
        self.route(ALLOWLIST + "?per_page=100&page=1", ok(first))
        self.route(ALLOWLIST + "?per_page=100&page=2", ok([project(2000, "acme/last")]))
        self.route(GROUPS, ok([]))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), {"enabled": True, "projects": 100, "groups": 0})

    def test_five_full_pages_leave_the_count_out(self):
        self.route(SCOPE, ok({"inbound_enabled": True}))
        self.route(ALLOWLIST, ok([project(1000 + i, f"acme/p{i}") for i in range(100)]))
        self.route(GROUPS, ok([]))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), {"enabled": True, "groups": 0})
        self.assertEqual(self.paths().count(SCOPE), 1)
        self.assertEqual(len([p for p in self.paths() if p.startswith(ALLOWLIST + "?")]), 5)

    # --- unknown, recorded --------------------------------------------------

    def test_forbidden_is_recorded_as_unknown(self):
        self.route(SCOPE, (403, {"message": "403 Forbidden"}, {}))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), {"error": "forbidden"})
        self.assertEqual(self.paths(), [SCOPE])  # not retried
        self.assertIn("Maintainer", result.stderr)

    def test_not_found_is_recorded_as_unknown(self):
        self.route(SCOPE, (404, {"message": "404 Project Not Found"}, {}))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), {"error": "not_found"})
        self.assertEqual(self.paths(), [SCOPE])

    # --- unknown, nothing written ------------------------------------------

    def assert_nothing_written(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.collected(), [])

    def test_unauthorized_writes_nothing(self):
        self.route(SCOPE, (401, {"message": "401 Unauthorized"}, {}))
        result = self.run_script()
        self.assert_nothing_written(result)
        self.assertEqual(self.paths(), [SCOPE])
        self.assertIn("HTTP 401", result.stderr)

    def test_server_error_retries_then_writes_nothing(self):
        self.route(SCOPE, (503, "upstream unavailable", {}))
        result = self.run_script()
        self.assert_nothing_written(result)
        self.assertEqual(self.paths(), [SCOPE] * 3)
        self.assertEqual(self.sleeps(), ["1", "2"])

    def test_recovers_after_a_server_error(self):
        self.route(SCOPE, (500, "boom", {}), ok({"inbound_enabled": False}))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), {"enabled": False})
        self.assertEqual(self.paths(), [SCOPE] * 2)

    def test_rate_limit_waits_retry_after(self):
        self.route(SCOPE, (429, "Retry later", {"Retry-After": "7"}), ok({"inbound_enabled": False}))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sleeps(), ["7"])
        self.assertEqual(self.written(), {"enabled": False})

    def test_retry_after_is_capped(self):
        self.route(SCOPE, (429, "Retry later", {"Retry-After": "3600"}))
        result = self.run_script()
        self.assert_nothing_written(result)
        self.assertEqual(self.sleeps(), ["60", "60"])

    def test_network_failure_writes_nothing(self):
        with socket.socket() as s:  # a port nothing listens on
            s.bind(("127.0.0.1", 0))
            closed = s.getsockname()[1]
        self.point_curl_at(closed)
        result = self.run_script()
        self.assert_nothing_written(result)
        self.assertEqual(self.sleeps(), ["1", "2"])
        self.assertIn("no response", result.stderr)

    def test_redirect_is_not_followed(self):
        # e.g. an SSO proxy in front of the API; the token must not follow it.
        self.route(SCOPE, (302, "", {"Location": f"https://{HOST}/users/sign_in"}))
        result = self.run_script()
        self.assert_nothing_written(result)
        self.assertEqual(self.paths(), [SCOPE])

    def test_malformed_answers_write_nothing(self):
        for body in ("<html>Sign in</html>", {}, {"outbound_enabled": False},
                     {"inbound_enabled": "true"}, {"inbound_enabled": None}, [],
                     '{"inbound_enabled": true}{"inbound_enabled": false}'):
            with self.subTest(body=body):
                self.reset()
                self.route(SCOPE, ok(body))
                result = self.run_script()
                self.assert_nothing_written(result)
                self.assertEqual(self.paths(), [SCOPE])

    # --- counts that can't be read -------------------------------------------

    def test_failed_count_is_left_out(self):
        self.route(SCOPE, ok({"inbound_enabled": True}))
        self.route(ALLOWLIST, (500, "boom", {}))
        self.route(GROUPS, ok([{"id": 100}, {"id": 101}]))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), {"enabled": True, "groups": 2})

    def test_non_list_count_is_left_out(self):
        self.route(SCOPE, ok({"inbound_enabled": True}))
        self.route(ALLOWLIST, ok([project(42, "acme/platform/backend")]))
        self.route(GROUPS, ok({"message": "unexpected"}))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), {"enabled": True, "projects": 0})

    # --- addressing -----------------------------------------------------------

    def test_path_is_the_fallback_without_a_project_id(self):
        enc = "/api/v4/projects/acme%2Fplatform%2Fbackend/job_token_scope"
        for meta in (None, "", '{"owner": "team-a"}', '{"project_id": "not-a-number"}'):
            with self.subTest(meta=meta):
                self.reset()
                self.route(enc, ok({"inbound_enabled": True}))
                # Without an id, self is matched by path, case-insensitively.
                self.route(enc + "/allowlist", ok([project(42, "Acme/Platform/Backend"), project(7, "acme/deployer")]))
                self.route(enc + "/groups_allowlist", ok([]))
                result = self.run_script(meta=meta)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.written(), {"enabled": True, "projects": 1, "groups": 0})
                self.assertEqual(self.paths()[0], enc)

    def test_project_count_left_out_when_self_is_not_listed(self):
        # Addressed by an outdated path, the list names the project by its new path.
        enc = "/api/v4/projects/acme%2Fplatform%2Fbackend/job_token_scope"
        self.route(enc, ok({"inbound_enabled": True}))
        self.route(enc + "/allowlist", ok([project(42, "acme/renamed-backend"), project(7, "acme/deployer")]))
        self.route(enc + "/groups_allowlist", ok([{"id": 100}]))
        result = self.run_script(meta=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.written(), {"enabled": True, "groups": 1})

    def test_numeric_project_id_in_meta(self):
        self.route(SCOPE, ok({"inbound_enabled": False}))
        result = self.run_script(meta='{"project_id": 42}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.paths(), [SCOPE])

    def test_dedicated_token_is_preferred(self):
        for gl_token in (TOKEN, None):
            with self.subTest(gl_token=gl_token):
                self.reset()
                self.route(SCOPE, ok({"inbound_enabled": False}))
                result = self.run_script(LUNAR_SECRET_GL_TOKEN=gl_token,
                                         LUNAR_SECRET_GL_JOB_TOKEN_SCOPE_TOKEN=SCOPE_TOKEN)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.written(), {"enabled": False})
                self.assertEqual([r["token"] for r in self.server.requests], [SCOPE_TOKEN])

    def test_denied_read_names_the_token_used(self):
        self.route(SCOPE, (403, {"message": "403 Forbidden"}, {}))
        result = self.run_script(LUNAR_SECRET_GL_JOB_TOKEN_SCOPE_TOKEN=SCOPE_TOKEN)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GL_JOB_TOKEN_SCOPE_TOKEN's user needs the Maintainer role", result.stderr)

    # --- not run -------------------------------------------------------------

    def test_other_host_is_skipped(self):
        result = self.run_script(LUNAR_COMPONENT_ID="github.com/acme/backend")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.collected(), [])
        self.assertEqual(self.paths(), [])

    def test_missing_token_errors(self):
        result = self.run_script(LUNAR_SECRET_GL_TOKEN=None)
        self.assert_nothing_written(result)
        self.assertEqual(self.paths(), [])


if __name__ == "__main__":
    unittest.main()
