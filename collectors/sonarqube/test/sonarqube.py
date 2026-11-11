#!/usr/bin/env python3
"""SonarQube Web API stand-in for test/run.sh.

Serves the endpoints the api sub-collector reads. Like the real server,
api/project_analyses/search has no pullRequest param: it answers for the
branch param, or the main branch without one.

GET /__load?file=<scenario.json> swaps in a scenario and clears the request log:
  {"analyses": {"<branch>": ["<revision>", ...]},   newest analysis, per poll
   "pull_requests": [[<entry>, ...], ...]}          PR list, per poll
Each list is served in order and its last item repeats, which models an
analysis landing mid-poll. {"status": 500} in place of a PR list fails that poll.

Usage: sonarqube.py <request-log> <port-file>
"""
import json
import sys
from base64 import b64encode
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

LOG, PORT_FILE = sys.argv[1], sys.argv[2]
AUTH = "Basic " + b64encode(b"test-token:").decode()

# Measures differ by scope so the test can tell PR data from branch data.
MEASURES = {
    "pr": {
        "alert_status": "ERROR", "coverage": "91.5", "duplicated_lines_density": "0.4",
        "bugs": "2", "vulnerabilities": "0", "code_smells": "5", "security_hotspots": "1",
        "ncloc": "1200", "reliability_rating": "3.0", "security_rating": "1.0",
        "sqale_rating": "1.0", "security_review_rating": "2.0", "sqale_index": "30",
    },
    "branch": {
        "alert_status": "OK", "coverage": "78.3", "duplicated_lines_density": "3.1",
        "bugs": "3", "vulnerabilities": "1", "code_smells": "42", "security_hotspots": "4",
        "ncloc": "12500", "reliability_rating": "1.0", "security_rating": "2.0",
        "sqale_rating": "1.0", "security_review_rating": "1.0", "sqale_index": "480",
    },
}
GATE = {
    "pr": {"status": "ERROR", "conditions": [{"status": "ERROR"}, {"status": "OK"}]},
    "branch": {"status": "OK", "conditions": [{"status": "OK"}]},
}
ISSUES = {
    "pr": {"total": 7, "facets": [{"property": "severities", "values": [
        {"val": "CRITICAL", "count": 1}, {"val": "MAJOR", "count": 2}, {"val": "MINOR", "count": 4}]}]},
    "branch": {"total": 46, "facets": [{"property": "severities", "values": [
        {"val": "MAJOR", "count": 1}, {"val": "MINOR", "count": 3}, {"val": "INFO", "count": 42}]}]},
}

scenario = {}
hits = {}


def nth(seq, key):
    i = hits.get(key, 0)
    hits[key] = i + 1
    return seq[min(i, len(seq) - 1)]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        global scenario
        url = urlsplit(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path == "/__load":
            with open(q["file"]) as f:
                scenario = json.load(f)
            hits.clear()
            open(LOG, "w").close()
            return self.reply(200, {})

        with open(LOG, "a") as f:
            f.write(self.path + "\n")
        if self.headers.get("Authorization") != AUTH:
            return self.reply(401, {"errors": [{"msg": "Not authorized"}]})
        scope = "pr" if "pullRequest" in q else "branch"

        if url.path == "/api/project_analyses/search":
            branch = q.get("branch", "main")
            revisions = scenario.get("analyses", {}).get(branch)
            if not revisions:
                if "branch" in q:
                    return self.reply(404, {"errors": [{"msg": f"Component '{q.get('project')}' on branch '{branch}' not found"}]})
                return self.reply(200, {"analyses": []})
            rev = nth(revisions, "analyses:" + branch)
            return self.reply(200, {"analyses": [{"key": "AX-" + rev[:8], "date": "2026-11-10T10:05:00+0000", "revision": rev}]})

        if url.path == "/api/project_pull_requests/list":
            prs = nth(scenario.get("pull_requests", [[]]), "pull_requests")
            if isinstance(prs, dict):
                return self.reply(prs["status"], {"errors": [{"msg": "simulated failure"}]})
            return self.reply(200, {"pullRequests": prs})

        if url.path == "/api/measures/component":
            measures = [{"metric": k, "value": v} for k, v in MEASURES[scope].items()]
            return self.reply(200, {"component": {"key": q.get("component"), "measures": measures}})
        if url.path == "/api/qualitygates/project_status":
            return self.reply(200, {"projectStatus": GATE[scope]})
        if url.path == "/api/issues/search":
            return self.reply(200, ISSUES[scope])
        return self.reply(404, {"errors": [{"msg": "Unknown url : " + url.path}]})


server = HTTPServer(("127.0.0.1", 0), Handler)
with open(PORT_FILE, "w") as f:
    f.write(str(server.server_port))
server.serve_forever()
