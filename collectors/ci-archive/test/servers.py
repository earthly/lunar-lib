"""Local stand-ins for the GitHub Actions API, S3 and STS, for run.sh.

GitHub (HTTPS, 127.0.0.1:8443, the GHES /api/v3 layout): serves one run
attempt, its jobs, and a 302 from its logs endpoint to a signed-URL blob, like
the real API. Scenarios are keyed by run ID. Blob requests carrying an
Authorization header are rejected, so a leaked token fails the test.

S3 (HTTP, 127.0.0.1:9001, path-style): PUT stores an object only if the
request is SigV4-signed for us-east-1/s3 by a key the bucket accepts and the
body matches x-amz-content-sha256, the same checks AWS makes. Buckets named
ingress* stand for a bucket in another account: only the credentials STS hands
out for INGRESS_ROLE may write there. Every other bucket takes the static test
key. Objects land in $S3_DIR/<bucket>/<key> for run.sh to inspect.

STS (HTTP, 127.0.0.1:9002): the query-API GET form of sts:AssumeRole. It
answers only calls SigV4-signed for us-east-1/sts by a base key, session token
included, and grants only INGRESS_ROLE with EXTERNAL_ID, like a trust policy
with an sts:ExternalId condition. Session names go to $STS_LOG.
"""
import hashlib, hmac, io, json, os, re, ssl, sys, threading, urllib.parse, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "test-gh-token"
# Access key -> (secret, session token). The ASIA keys are temporary: AWS
# rejects them without their token.
KEYS = {
    "AKIATEST": ("secret-test", None),
    "ASIABASETEST": ("base/Secret+test", "IQoJb3JpZ2luX2VjE+base/session/token=="),
    "ASIAASSUMEDTEST": ("assumed/Secret+test", "IQoJb3JpZ2luX2VjE+assumed/session/token=="),
}
BASE_KEYS = {"AKIATEST", "ASIABASETEST"}
ASSUMED_KEY = "ASIAASSUMEDTEST"
INGRESS_ROLE = "arn:aws:iam::111122223333:role/ci-archive-ingress"
EXTERNAL_ID = "lunar-ext=test+1"
S3_DIR = os.environ["S3_DIR"]
STS_LOG = os.environ["STS_LOG"]
BASE = "https://127.0.0.1:8443"


def logs_zip(run_id, attempt, size=0):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("1_build.txt", f"2026-09-24T00:00:00Z run {run_id} attempt {attempt} log line\n")
        # GitHub also ships each step's slice of the job log in a folder per job.
        zf.writestr("build/1_Set up job.txt", f"2026-09-24T00:00:00Z run {run_id} attempt {attempt} log line\n")
        if size:
            zf.writestr("big.bin", os.urandom(size), compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


def attempt(run_id, n, name="build", status="completed", conclusion="success", jobs=2, event="push"):
    return {
        "id": run_id, "run_attempt": n, "name": name, "path": f".github/workflows/{name}.yml",
        "event": event, "head_branch": "main", "head_sha": f"sha-{run_id}", "status": status,
        "conclusion": conclusion if status == "completed" else None,
        "run_started_at": f"2026-09-24T00:0{n}:00Z", "updated_at": f"2026-09-24T00:0{n}:30Z",
        "html_url": f"https://example.test/acme/widgets/actions/runs/{run_id}/attempts/{n}",
        "pull_requests": [], "_jobs": jobs,
    }


# (run id, attempt) -> the attempt. Log behaviour is keyed by run id below.
ATTEMPTS = {(a["id"], a["run_attempt"]): a for a in [
    attempt(101, 1, conclusion="failure"), attempt(101, 2),
    attempt(104, 1, status="in_progress"),
    attempt(105, 1, name="nightly"),
    attempt(201, 1),
    attempt(301, 1),
    attempt(401, 1),
    attempt(501, 1, jobs=150),
    attempt(601, 1, name="promote", event="workflow_run"),
]}
EXPIRED = {105}                 # logs endpoint answers 410
BIG = {201: 1_500_000}          # bytes of incompressible log
flaky_left = {301: 1}           # the attempt endpoint 502s this many times first
lagging_left = {401: 1}         # the logs endpoint 404s this many times first
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
            run_id, n = (int(x) for x in parts[1].split(".")[0].split("-"))
            return self.send(200, logs_zip(run_id, n, BIG.get(run_id, 0)), "application/zip")
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            return self.send(401, b'{"message":"Bad credentials"}')
        # /api/v3/repos/acme/widgets/actions/runs/<id>/attempts/<n>[/jobs|/logs]
        if parts[:7] != ["api", "v3", "repos", "acme", "widgets", "actions", "runs"] or len(parts) < 10 \
                or parts[8] != "attempts":
            return self.send(404, b'{"message":"Not Found"}')
        run_id, n = int(parts[7]), int(parts[9])
        found = ATTEMPTS.get((run_id, n))
        if not found:
            return self.send(404, b'{"message":"Not Found"}')
        rest = parts[10:]
        if not rest:
            with lock:
                if flaky_left.get(run_id, 0) > 0:
                    flaky_left[run_id] -= 1
                    return self.send(502, b'{"message":"bad gateway"}')
            body = {k: v for k, v in found.items() if not k.startswith("_")}
            return self.send(200, json.dumps(body).encode())
        if rest == ["jobs"]:
            q = urllib.parse.parse_qs(url.query)
            per, page = int(q.get("per_page", ["30"])[0]), int(q.get("page", ["1"])[0])
            jobs = [{"id": run_id * 1000 + i, "name": f"job-{i}", "conclusion": found["conclusion"],
                     "started_at": found["run_started_at"], "completed_at": found["updated_at"],
                     "html_url": f"https://example.test/job/{i}",
                     "steps": [{"number": 1, "name": "Run", "conclusion": found["conclusion"]}]}
                    for i in range(found["_jobs"])]
            return self.send(200, json.dumps({"total_count": len(jobs), "jobs": jobs[(page - 1) * per: page * per]}).encode())
        if rest == ["logs"]:
            if run_id in EXPIRED:
                return self.send(410, b'{"message":"Gone"}')
            with lock:
                if lagging_left.get(run_id, 0) > 0:
                    lagging_left[run_id] -= 1
                    return self.send(404, b'{"message":"Not Found"}')
            return self.send(302, headers={"Location": f"{BASE}/blob/{run_id}-{n}.zip?sig=abc"})
        return self.send(404, b'{"message":"Not Found"}')


def aws_error(h, status, code, sts=False):
    body = (f"<ErrorResponse><Error><Code>{code}</Code></Error></ErrorResponse>" if sts
            else f"<Error><Code>{code}</Code></Error>").encode()
    h.send_response(status)
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def canonical_query(query):
    """The SigV4 canonical query string: each name and value decoded, then
    RFC 3986-encoded with upper-case hex, sorted."""
    enc = lambda x: urllib.parse.quote(urllib.parse.unquote(x), safe="-_.~")
    pairs = sorted((enc(k), enc(v)) for k, _, v in (p.partition("=") for p in query.split("&") if p))
    return "&".join(f"{k}={v}" for k, v in pairs)


def sigv4_signer(h, service, payload_hash):
    """(access key, None) if the request is validly SigV4-signed for
    us-east-1/<service> by a key in KEYS, its session token sent and signed;
    else (None, the error code AWS would return)."""
    auth = h.headers.get("Authorization", "")
    if not auth.startswith("AWS4-HMAC-SHA256 "):
        return None, "AccessDenied"
    f = dict(x.strip().split("=", 1) for x in auth[len("AWS4-HMAC-SHA256 "):].split(","))
    akid, day, region, svc, _ = f["Credential"].split("/")
    if akid not in KEYS:
        return None, "InvalidAccessKeyId"
    secret, token = KEYS[akid]
    signed = f["SignedHeaders"].split(";")
    if token is not None and (h.headers.get("x-amz-security-token") != token
                              or "x-amz-security-token" not in signed):
        return None, "InvalidToken"
    if (region, svc) != ("us-east-1", service) or (service == "s3" and "x-amz-content-sha256" not in signed):
        return None, "SignatureDoesNotMatch"
    path, _, query = h.path.partition("?")
    canon_uri = urllib.parse.quote(urllib.parse.unquote(path), safe="/-_.~")
    canon_hdrs = "".join(f"{n}:{' '.join(h.headers[n].split())}\n" for n in signed)
    creq = "\n".join([h.command, canon_uri, canonical_query(query), canon_hdrs, ";".join(signed), payload_hash])
    scope = f"{day}/{region}/{svc}/aws4_request"
    sts = "\n".join(["AWS4-HMAC-SHA256", h.headers["x-amz-date"], scope,
                     hashlib.sha256(creq.encode()).hexdigest()])
    k = ("AWS4" + secret).encode()
    for part in (day, region, svc, "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    if hmac.new(k, sts.encode(), hashlib.sha256).hexdigest() != f["Signature"]:
        return None, "SignatureDoesNotMatch"
    return akid, None


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
        akid, problem = sigv4_signer(self, "s3", declared)
        if problem:
            return aws_error(self, 403, problem)
        bucket = urllib.parse.unquote(self.path.lstrip("/")).split("/", 1)[0]
        if akid != (ASSUMED_KEY if bucket.startswith("ingress") else "AKIATEST"):
            return aws_error(self, 403, "AccessDenied")
        if declared != hashlib.sha256(body).hexdigest():
            return aws_error(self, 400, "XAmzContentSHA256Mismatch")
        dest = os.path.join(S3_DIR, urllib.parse.unquote(self.path.lstrip("/")))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as out:
            out.write(body)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()


class STS(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        akid, problem = sigv4_signer(self, "sts", hashlib.sha256(b"").hexdigest())
        if problem:
            return aws_error(self, 403, problem, sts=True)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        if q.get("Action") != "AssumeRole" or q.get("Version") != "2011-06-15":
            return aws_error(self, 400, "InvalidAction", sts=True)
        session = q.get("RoleSessionName", "")
        if not re.fullmatch(r"[\w+=,.@-]{2,64}", session):
            return aws_error(self, 400, "ValidationError", sts=True)
        if akid not in BASE_KEYS or q.get("RoleArn") != INGRESS_ROLE or q.get("ExternalId") != EXTERNAL_ID:
            return aws_error(self, 403, "AccessDenied", sts=True)
        with lock, open(STS_LOG, "a") as out:
            out.write(session + "\n")
        secret, token = KEYS[ASSUMED_KEY]
        body = (f'<AssumeRoleResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/"><AssumeRoleResult>'
                f"<Credentials><AccessKeyId>{ASSUMED_KEY}</AccessKeyId><SecretAccessKey>{secret}</SecretAccessKey>"
                f"<SessionToken>{token}</SessionToken><Expiration>2026-09-24T01:00:00Z</Expiration></Credentials>"
                f"</AssumeRoleResult></AssumeRoleResponse>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


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
    serve(ThreadingHTTPServer(("127.0.0.1", 9002), STS))
    print("ready", flush=True)
    threading.Event().wait()
