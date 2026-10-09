#!/usr/bin/env python3
"""Tests for ticket_path: where the jira sub-collectors record their ticket.

The scripts run for real as subprocesses. `lunar` and `psql` are stubbed on
PATH, GitHub's PR endpoint is answered by a curl shim, and Jira is a local HTTP
server serving fixtures/jira-issue-*.json — the Get issue example from
Atlassian's REST API v3 reference with the fields these tests need added — so
curl and the scripts' Jira handling run unmodified.

The PR's title names the delivery ticket (TP-1) and its description an
architecture-review submission (ARB-56), which is the pair a second import
exists to record side by side.
"""

import http.server
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECTOR = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")
REAL_CURL = shutil.which("curl")

PR = {
    "title": "[TP-1] Add payment retries",
    "description": "Architecture review: ARB-56\n\nTicket: TP-1",
}
SECOND = {
    "LUNAR_VAR_TICKET_PATTERN": "ARB-[0-9]+",
    "LUNAR_VAR_TICKET_PATH": ".vcs.pr.architecture_review",
}


def load_issue(key):
    with open(os.path.join(FIXTURES, f"jira-issue-{key}.json")) as f:
        return json.load(f)


class JiraStandIn:
    """Answers GET /rest/api/3/issue/{key} like Jira: 200 with the issue, or
    404 with Jira's error body for a key it does not know."""

    def __init__(self, issues):
        self.requests = []
        stand_in = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                stand_in.requests.append(self.path)
                prefix = "/rest/api/3/issue/"
                key = self.path[len(prefix):] if self.path.startswith(prefix) else ""
                if key in issues:
                    status, body = 200, issues[key]
                else:
                    status, body = 404, {
                        "errorMessages": ["Issue does not exist or you do not have permission to see it."],
                        "errors": {},
                    }
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jira-path-test-")
        self.bin = os.path.join(self.tmp, "bin")
        self.mock = os.path.join(self.tmp, "mock")
        os.makedirs(self.bin)
        os.makedirs(self.mock)
        self.capture = os.path.join(self.tmp, "calls.jsonl")
        self.jira = JiraStandIn({k: load_issue(k) for k in ("TP-1", "ARB-56")})
        self.addCleanup(self.jira.close)

        with open(os.path.join(self.mock, "pr.json"), "w") as f:
            json.dump({"vcs": {"pr": PR}}, f)
        with open(os.path.join(self.mock, "github-pr.json"), "w") as f:
            json.dump({"number": 8, "title": PR["title"], "body": PR["description"]}, f)

        # lunar: serves the PR-scoped Component JSON and a SQL connection
        # string, and logs every call with its argv and piped stdin.
        self._stub("lunar", """\
            #!/usr/bin/env python3
            import json, os, sys
            argv = sys.argv[1:]
            rec = {"argv": argv}
            if argv[:2] == ["component", "get-json"]:
                sys.stdout.write(open(os.path.join(os.environ["MOCK_DIR"], "pr.json")).read())
            elif argv[:2] == ["sql", "connection-string"]:
                print("postgres://stub")
            elif argv[-1:] == ["-"]:
                rec["stdin"] = sys.stdin.read()
            with open(os.environ["CAPTURE"], "a") as f:
                f.write(json.dumps(rec) + "\\n")
            """)
        # psql: records the query and answers with a reuse count.
        self._stub("psql", """\
            #!/usr/bin/env python3
            import json, os, sys
            with open(os.environ["CAPTURE"], "a") as f:
                f.write(json.dumps({"psql": sys.argv[1:]}) + "\\n")
            print("2")
            """)
        # curl: answers GitHub's PR endpoint, hands everything else (Jira) to
        # the real curl.
        self._stub("curl", f"""\
            #!/bin/sh
            for a in "$@"; do
              case "$a" in
                https://api.github.com/*) cat "$MOCK_DIR/github-pr.json"; exit 0 ;;
              esac
            done
            exec {REAL_CURL} "$@"
            """)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stub(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write(textwrap.dedent(body))
        os.chmod(path, 0o755)

    def run_script(self, script, extra=None):
        env = {
            "PATH": self.bin + ":" + os.environ["PATH"],
            "MOCK_DIR": self.mock,
            "CAPTURE": self.capture,
            "LUNAR_COMPONENT_ID": "github.com/acme/backend",
            "LUNAR_COMPONENT_PR": "8",
            "LUNAR_SECRET_GH_TOKEN": "gh-token",
            "LUNAR_VAR_JIRA_BASE_URL": self.jira.url,
            "LUNAR_VAR_JIRA_USER": "lunar@acme.com",
            "LUNAR_SECRET_JIRA_TOKEN": "jira-token",
            "LUNAR_VAR_JIRA_RETRIES": "0",
        }
        env.update(extra or {})
        result = subprocess.run(
            ["bash", os.path.join(COLLECTOR, script)],
            env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        )
        calls = []
        if os.path.exists(self.capture):
            with open(self.capture) as f:
                calls = [json.loads(line) for line in f if line.strip()]
        return result, calls

    @staticmethod
    def collected(calls):
        """Every value written by `lunar collect`, keyed by path."""
        out = {}
        for call in calls:
            argv = call.get("argv", [])
            if argv[:1] != ["collect"]:
                continue
            if argv[1:2] == ["-j"]:
                raw = call["stdin"] if argv[3] == "-" else argv[3]
                out[argv[2]] = json.loads(raw)
            else:
                pairs = argv[1:]
                out.update(zip(pairs[0::2], pairs[1::2]))
        return out


class TicketPathTest(Base):
    def test_default_path_records_the_delivery_ticket_at_vcs_pr_ticket(self):
        result, calls = self.run_script("ticket_from_json.sh")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        got = self.collected(calls)
        self.assertEqual(got[".vcs.pr.ticket.id"], "TP-1")
        self.assertIs(got[".vcs.pr.ticket.valid"], True)
        self.assertEqual(got[".vcs.pr.ticket.status"], "In Progress")
        self.assertEqual(got[".vcs.pr.ticket.native.jira"]["key"], "TP-1")
        self.assertTrue(all(p.startswith(".vcs.pr.ticket.") for p in got), msg=sorted(got))

    def test_ticket_path_records_the_second_reference_at_its_own_path(self):
        result, calls = self.run_script("ticket_from_json.sh", SECOND)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        got = self.collected(calls)
        root = ".vcs.pr.architecture_review"
        self.assertEqual(got[f"{root}.id"], "ARB-56")
        self.assertEqual(got[f"{root}.url"], f"{self.jira.url}/browse/ARB-56")
        self.assertEqual(got[f"{root}.source"], {"tool": "jira", "integration": "api"})
        self.assertIs(got[f"{root}.valid"], True)
        self.assertEqual(got[f"{root}.status"], "Approved")
        self.assertEqual(got[f"{root}.type"], "Submission")
        self.assertEqual(got[f"{root}.assignee"], "mia@example.com")
        native = got[f"{root}.native.jira"]
        self.assertEqual(native["fields"]["customfield_10042"]["value"], "Payments")
        # Nothing lands on the delivery ticket's path.
        self.assertTrue(all(p.startswith(root + ".") for p in got), msg=sorted(got))

    def test_ticket_sh_honours_ticket_path(self):
        result, calls = self.run_script("ticket.sh", SECOND)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        got = self.collected(calls)
        self.assertEqual(got[".vcs.pr.architecture_review.id"], "ARB-56")
        self.assertEqual(got[".vcs.pr.architecture_review.status"], "Approved")
        self.assertFalse([p for p in got if p.startswith(".vcs.pr.ticket")], msg=sorted(got))

    def test_unconfirmed_reference_records_tracker_error_at_ticket_path(self):
        with open(os.path.join(self.mock, "pr.json"), "w") as f:
            json.dump({"vcs": {"pr": {"title": "[TP-1] x", "description": "Review: ARB-99"}}}, f)
        result, calls = self.run_script("ticket_from_json.sh", SECOND)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        got = self.collected(calls)
        self.assertEqual(got[".vcs.pr.architecture_review.id"], "ARB-99")
        self.assertEqual(got[".vcs.pr.architecture_review.tracker_error"], "not_found")
        self.assertNotIn(".vcs.pr.architecture_review.valid", got)

    def test_path_without_the_leading_dot_is_accepted(self):
        result, calls = self.run_script(
            "ticket_from_json.sh", dict(SECOND, LUNAR_VAR_TICKET_PATH="vcs.pr.architecture_review"))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self.collected(calls)[".vcs.pr.architecture_review.id"], "ARB-56")

    def test_empty_ticket_path_means_the_default(self):
        result, calls = self.run_script("ticket_from_json.sh", {"LUNAR_VAR_TICKET_PATH": ""})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self.collected(calls)[".vcs.pr.ticket.id"], "TP-1")

    def test_invalid_ticket_path_fails_before_reading_anything(self):
        for bad in (".vcs.pr", ".vcs.prx.a", ".sca.review", ".vcs.pr.arch-review",
                    ".vcs.pr.a b", ".vcs.pr.x'||1", ".vcs.pr..x"):
            for script in ("ticket_from_json.sh", "ticket.sh", "ticket-history.sh"):
                with self.subTest(path=bad, script=script):
                    if os.path.exists(self.capture):
                        os.remove(self.capture)
                    result, calls = self.run_script(script, {"LUNAR_VAR_TICKET_PATH": bad})
                    self.assertEqual(result.returncode, 1, msg=result.stderr)
                    self.assertIn("ticket_path must be", result.stderr)
                    self.assertEqual(calls, [])
                    self.assertEqual(self.jira.requests, [])

    def test_single_project_pattern_with_prefix_still_resolves(self):
        # A delivery import restricted to one project key and a bracket prefix
        # is untouched by ticket_path.
        result, calls = self.run_script("ticket_from_json.sh", {
            "LUNAR_VAR_TICKET_PATTERN": "TP-[0-9]+",
            "LUNAR_VAR_TICKET_PREFIX": "[",
            "LUNAR_VAR_TICKET_SUFFIX": "]",
        })
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self.collected(calls)[".vcs.pr.ticket.id"], "TP-1")


class TicketHistoryPathTest(Base):
    def query(self, calls):
        queries = [c["psql"][c["psql"].index("-c") + 1] for c in calls if "psql" in c]
        self.assertEqual(len(queries), 1, msg=calls)
        return queries[0]

    def test_default_path_query_and_write_are_unchanged(self):
        result, calls = self.run_script("ticket-history.sh")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("AND component_json->'vcs'->'pr'->'ticket'->>'id' = 'TP-1'", self.query(calls))
        self.assertEqual(self.collected(calls), {".vcs.pr.ticket.reuse_count": 2})

    def test_ticket_path_counts_and_records_reuse_of_the_second_reference(self):
        result, calls = self.run_script("ticket-history.sh", SECOND)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn(
            "AND component_json->'vcs'->'pr'->'architecture_review'->>'id' = 'ARB-56'",
            self.query(calls))
        self.assertEqual(self.collected(calls), {".vcs.pr.architecture_review.reuse_count": 2})


if __name__ == "__main__":
    unittest.main()
