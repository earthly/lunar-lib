"""Shared harness for driving the collector scripts with stubbed tools.

Each test runs a real script with `curl`, `lunar` and `sleep` stubs first on
PATH. The curl stub answers from fixture files chosen by route: a route matches
when all its substrings appear in the request URL plus GraphQL query, and
optionally when the URL ends with a given path or the request's `cursor`
variable equals a given value. The first matching route wins. Each
route serves its `codes` in order (repeating the last), so one call site can
fail and then recover. The lunar stub records every `lunar collect` call, and
`component_json()` folds them back into the JSON the hub would merge.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
PLUGIN = os.path.dirname(HERE)

CURL_STUB = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys

    args = sys.argv[1:]
    url = args[-1]
    payload = {}
    if "@-" in args:
        payload = json.loads(sys.stdin.read() or "{}")
    mock = os.environ["MOCK_DIR"]
    with open(os.path.join(mock, "requests.jsonl"), "a") as f:
        f.write(json.dumps({"url": url, "payload": payload}) + "\\n")
    key = url + " " + payload.get("query", "")
    cursor = (payload.get("variables") or {}).get("cursor")
    with open(os.path.join(mock, "routes.json")) as f:
        routes = json.load(f)
    for i, route in enumerate(routes):
        if not all(m in key for m in route["match"]):
            continue
        if "endswith" in route and not url.endswith(route["endswith"]):
            continue
        if "cursor" in route and route["cursor"] != cursor:
            continue
        counter = os.path.join(mock, f"route{i}.n")
        n = int(open(counter).read()) if os.path.exists(counter) else 0
        open(counter, "w").write(str(n + 1))
        codes = route["codes"]
        code = codes[min(n, len(codes) - 1)]
        if code == "NETFAIL":
            sys.exit(6)
        break
    else:
        route, code = {"body": '{"message":"Not Found"}'}, "404"
    # Like real curl, the status is appended only when asked for with -w.
    sys.stdout.write(route["body"] + ("\\n" + code if "-w" in args else ""))
    """
)

# Records each `lunar collect` call twice: the joined argv (for substring
# assertions) and as JSON with any piped value (for component_json()).
LUNAR_STUB = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys

    args = sys.argv[1:]
    if args[:1] != ["collect"]:
        sys.exit(0)
    capture = os.environ["LUNAR_CAPTURE"]
    with open(capture, "a") as f:
        f.write(" ".join(args) + "\\n")
    rest = args[1:]
    rec = {"json": False, "pairs": []}
    if rest[:1] == ["-j"]:
        rec["json"], rest = True, rest[1:]
    for path, value in zip(rest[0::2], rest[1::2]):
        rec["pairs"].append([path, sys.stdin.read() if value == "-" else value])
    with open(capture + ".jsonl", "a") as f:
        f.write(json.dumps(rec) + "\\n")
    """
)


def fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return f.read()


def fixture_json(name):
    return json.loads(fixture(name))


def merge(a, b):
    """The hub's merge: objects recurse, arrays concatenate, scalars replace."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k, v in b.items():
            a[k] = merge(a[k], v) if k in a else v
        return a
    if isinstance(a, list) and isinstance(b, list):
        return a + b
    return b


class ScriptTestCase(unittest.TestCase):
    script = None  # file name under the plugin directory

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="github-collector-test-")
        self.bin = os.path.join(self.tmp, "bin")
        self.mock = os.path.join(self.tmp, "mock")
        os.makedirs(self.bin)
        os.makedirs(self.mock)
        self.capture = os.path.join(self.tmp, "collect.log")
        self.routes = []
        self._stub("curl", CURL_STUB)
        self._stub("lunar", LUNAR_STUB)
        self._stub("sleep", "#!/bin/sh\nexit 0\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stub(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, 0o755)

    def route(self, *match, endswith=None, body="{}", codes=("200",), cursor=Ellipsis):
        route = {"match": list(match), "body": body, "codes": list(codes)}
        if endswith is not None:
            route["endswith"] = endswith
        if cursor is not Ellipsis:
            route["cursor"] = cursor
        self.routes.append(route)

    def run_script(self, **env_overrides):
        with open(os.path.join(self.mock, "routes.json"), "w") as f:
            json.dump(self.routes, f)
        env = {k: v for k, v in os.environ.items() if not k.startswith("LUNAR_")}
        env["PATH"] = self.bin + os.pathsep + env.get("PATH", "")
        env["MOCK_DIR"] = self.mock
        env["LUNAR_CAPTURE"] = self.capture
        env["LUNAR_COMPONENT_ID"] = "github.com/acme/widget"
        env["LUNAR_SECRET_GH_TOKEN"] = "fake-token"
        for k, v in env_overrides.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        proc = subprocess.run(
            ["bash", os.path.join(PLUGIN, self.script)],
            env=env, capture_output=True, text=True,
        )
        return proc.returncode, proc.stderr

    def collected(self):
        if not os.path.exists(self.capture):
            return ""
        with open(self.capture) as f:
            return f.read()

    def component_json(self):
        out = {}
        path = self.capture + ".jsonl"
        if not os.path.exists(path):
            return out
        with open(path) as f:
            for line in f:
                rec = json.loads(line)
                for dotted, raw in rec["pairs"]:
                    value = json.loads(raw) if rec["json"] else raw
                    for key in reversed(dotted.lstrip(".").split(".")):
                        value = {key: value}
                    out = merge(out, value)
        return out

    def requests(self):
        path = os.path.join(self.mock, "requests.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f]
