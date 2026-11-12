#!/usr/bin/env python3
"""GitHub REST API stand-in for test/run-github-app.sh.

Serves a commit's check runs at /<host>/<API path>: github.com's API at
/github.com/repos/..., a GitHub Enterprise Server's at /<host>/api/v3/repos/...
The harness's curl wrapper rewrites the collector's real URLs to that shape, so
a call sent to the wrong API base for its host gets a 404.

GET /__load?file=<scenario.json> swaps in a scenario and clears the request log:
  {"polls": [<poll>, ...]}
One poll per collector poll (page 1 starts the next one), the last repeating.
A poll is a list of check runs, served per_page at a time, or
{"status": <code>, "message": "..."} to fail that poll.

Each request is logged as "<host> <path>?<query> <token>".

Usage: github_api.py <request-log> <port-file>
"""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

LOG, PORT_FILE = sys.argv[1], sys.argv[2]
REPO = "acme/widgets"
CHECK_RUNS = re.compile(r"^/repos/([^/]+/[^/]+)/commits/([0-9a-f]{40})/check-runs$")

scenario = {}
state = {"poll": 0, "current": None}


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
            state.update(poll=0, current=None)
            open(LOG, "w").close()
            return self.reply(200, {})

        host, _, rest = url.path.lstrip("/").partition("/")
        auth = self.headers.get("Authorization", "")
        token = auth[len("token "):] if auth.startswith("token ") else "-"
        with open(LOG, "a") as f:
            f.write(f"{host} /{rest}{'?' + url.query if url.query else ''} {token}\n")

        path = "/" + rest
        if host != "github.com":
            if not path.startswith("/api/v3/"):
                return self.reply(404, {"message": "Not Found"})
            path = path[len("/api/v3"):]
        if token == "-":
            return self.reply(401, {"message": "Requires authentication"})
        m = CHECK_RUNS.match(path)
        if not m or m.group(1) != REPO:
            return self.reply(404, {"message": "Not Found"})

        page, per_page = int(q.get("page", "1")), int(q.get("per_page", "30"))
        if page == 1 or state["current"] is None:
            polls = scenario.get("polls", [[]])
            state["current"] = polls[min(state["poll"], len(polls) - 1)]
            state["poll"] += 1
        poll = state["current"]
        if isinstance(poll, dict):
            return self.reply(poll["status"], {"message": poll.get("message", "simulated failure")})
        runs = poll[(page - 1) * per_page:page * per_page]
        return self.reply(200, {"total_count": len(poll), "check_runs": runs})


server = HTTPServer(("127.0.0.1", 0), Handler)
with open(PORT_FILE, "w") as f:
    f.write(str(server.server_port))
server.serve_forever()
