"""Local stand-ins for the GitHub Actions API and S3, for run.sh.

GitHub (HTTPS, 127.0.0.1:8443, the GHES /api/v3 layout): lists runs by
head_sha and 302s each run's logs to a signed-URL blob, like the real API.
Scenarios are keyed by the sha. Blob requests carrying an Authorization header
are rejected, so a leaked token fails the test.

S3 (HTTP, 127.0.0.1:9001, path-style): PUT stores an object only if the
request is SigV4-signed with AKIATEST/secret-test for us-east-1/s3 and the
body matches x-amz-content-sha256, the same checks AWS makes. Objects land in
$S3_DIR/<bucket>/<key> for run.sh to inspect.
"""
import hashlib, hmac, io, json, os, ssl, sys, threading, urllib.parse, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "test-gh-token"
S3_KEY = ("AKIATEST", "secret-test")
S3_DIR = os.environ["S3_DIR"]
BASE = "https://127.0.0.1:8443"


def logs_zip(run_id, size=0):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("1_build.txt", f"2026-09-24T00:00:00Z run {run_id} log line\n")
        if size:
            zf.writestr("big.bin", os.urandom(size), compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


def run(run_id, name, status="completed", conclusion="success"):
    return {
        "id": run_id, "name": name, "path": f".github/workflows/{name}.yml",
        "event": "push", "status": status,
        "conclusion": conclusion if status == "completed" else None,
        "run_attempt": 1, "run_started_at": "2026-09-24T00:00:00Z",
        "updated_at": "2026-09-24T00:05:00Z",
        "html_url": f"https://example.test/acme/widgets/actions/runs/{run_id}",
    }


# sha -> list of runs. Log behaviour is keyed by run id below.
SCENARIOS = {
    "sha-multi": [run(101, "build"), run(102, "test", conclusion="failure"),
                  run(103, "lint"), run(104, "deploy", status="in_progress"),
                  run(105, "nightly")],
    "sha-none": [],
    "sha-big": [run(201, "build"), run(202, "test")],
    "sha-flaky": [run(301, "build")],
    "sha-paged": [run(1000 + i, f"job-{i}") for i in range(105)],
}
EXPIRED = {105}                 # logs endpoint answers 410
BIG = {201: 700_000, 202: 700_000}
flaky_left = {"sha-flaky": 1}   # listing 502s this many times first
lock = threading.Lock()


class GitHub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body=b"", ctype="application/json", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        parts = url.path.strip("/").split("/")
        if parts[0] == "blob":
            if "Authorization" in self.headers:
                return self.send(400, b'{"message":"token sent to blob host"}')
            run_id = int(parts[1].split(".")[0])
            return self.send(200, logs_zip(run_id, BIG.get(run_id, 0)), "application/zip")
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            return self.send(401, b'{"message":"Bad credentials"}')
        # /api/v3/repos/acme/widgets/actions/runs[/<id>/logs]
        if parts[:6] != ["api", "v3", "repos", "acme", "widgets", "actions"] or parts[6] != "runs":
            return self.send(404, b'{"message":"Not Found"}')
        if len(parts) == 7:
            q = urllib.parse.parse_qs(url.query)
            sha = q.get("head_sha", [""])[0]
            with lock:
                if flaky_left.get(sha, 0) > 0:
                    flaky_left[sha] -= 1
                    return self.send(502, b'{"message":"bad gateway"}')
            runs = SCENARIOS.get(sha, [])
            per, page = int(q.get("per_page", ["30"])[0]), int(q.get("page", ["1"])[0])
            body = {"total_count": len(runs), "workflow_runs": runs[(page - 1) * per: page * per]}
            return self.send(200, json.dumps(body).encode())
        run_id = int(parts[7])
        if run_id in EXPIRED:
            return self.send(410, b'{"message":"Gone"}')
        return self.send(302, headers={"Location": f"{BASE}/blob/{run_id}.zip?sig=abc"})


def s3_error(h, status, code):
    body = f"<Error><Code>{code}</Code></Error>".encode()
    h.send_response(status)
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def sigv4_problem(h, payload_hash):
    """None if the request is validly signed for S3_KEY, else a reason."""
    auth = h.headers.get("Authorization", "")
    if not auth.startswith("AWS4-HMAC-SHA256 "):
        return "no SigV4 Authorization header"
    f = dict(x.strip().split("=", 1) for x in auth[len("AWS4-HMAC-SHA256 "):].split(","))
    akid, day, region, svc, _ = f["Credential"].split("/")
    if (akid, region, svc) != (S3_KEY[0], "us-east-1", "s3"):
        return f"credential scope {akid}/{region}/{svc}"
    signed = f["SignedHeaders"].split(";")
    if "x-amz-content-sha256" not in signed:
        return "x-amz-content-sha256 not signed"
    path, _, query = h.path.partition("?")
    canon_uri = urllib.parse.quote(urllib.parse.unquote(path), safe="/-_.~")
    canon_hdrs = "".join(f"{n}:{' '.join(h.headers[n].split())}\n" for n in signed)
    creq = "\n".join([h.command, canon_uri, query, canon_hdrs, ";".join(signed), payload_hash])
    scope = f"{day}/{region}/{svc}/aws4_request"
    sts = "\n".join(["AWS4-HMAC-SHA256", h.headers["x-amz-date"], scope,
                     hashlib.sha256(creq.encode()).hexdigest()])
    k = ("AWS4" + S3_KEY[1]).encode()
    for part in (day, region, svc, "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    if hmac.new(k, sts.encode(), hashlib.sha256).hexdigest() != f["Signature"]:
        return "signature mismatch"
    return None


class S3(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_PUT(self):
        if self.headers.get("Expect", "").lower() == "100-continue":
            self.send_response_only(100)
            self.end_headers()
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        declared = self.headers.get("x-amz-content-sha256", "")
        if sigv4_problem(self, declared):
            return s3_error(self, 403, "SignatureDoesNotMatch")
        if declared != hashlib.sha256(body).hexdigest():
            return s3_error(self, 400, "XAmzContentSHA256Mismatch")
        dest = os.path.join(S3_DIR, urllib.parse.unquote(self.path.lstrip("/")))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as out:
            out.write(body)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()


def serve(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()


if __name__ == "__main__":
    cert, key = sys.argv[1], sys.argv[2]
    gh = ThreadingHTTPServer(("127.0.0.1", 8443), GitHub)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    gh.socket = ctx.wrap_socket(gh.socket, server_side=True)
    serve(gh)
    serve(ThreadingHTTPServer(("127.0.0.1", 9001), S3))
    print("ready", flush=True)
    threading.Event().wait()
