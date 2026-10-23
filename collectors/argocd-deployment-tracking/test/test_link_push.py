#!/usr/bin/env python3
"""Tests for link_push.sh's idempotency guard.

Before pushing an app set onto a target, the guard reads the target and skips
when it already carries that set. The regression locked in: the read must be
`--git-sha "$TSHA"`, the sha the push writes to. An unpinned read serves the
materialized copy, which can miss the prior push, so the guard pushes again
and the target's .cd.gitops.applications gains a duplicate.

The real script runs as a subprocess next to a stub parse.sh (one fixed
Application), with `lunar` and `psql` stubbed on PATH. The `lunar` stub serves
pinned.json to a --git-sha read and unpinned.json otherwise, and logs every
call to $CAPTURE.
"""

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(__file__)
COLLECTOR = os.path.abspath(os.path.join(HERE, ".."))

SELF = "github.com/acme/gitops"
TARGET = "github.com/acme/svc"
TSHA = "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"
APPS = ('{"applications":[{"name":"svc-prod","component_annotation":"%s",'
        '"images":[],"source_ref":{}}]}' % TARGET)
PRIOR_PUSH = ('{"cd":{"gitops":{"linked_from":"%s",'
              '"applications":[{"name":"svc-prod"}]}}}' % SELF)


class LinkPushGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="link-push-test-")
        self.bin = os.path.join(self.tmp, "bin")
        self.mock = os.path.join(self.tmp, "mock")
        self.script_dir = os.path.join(self.tmp, "collector")
        for d in (self.bin, self.mock, self.script_dir):
            os.makedirs(d)
        self.capture = os.path.join(self.tmp, "calls.log")
        shutil.copy(os.path.join(COLLECTOR, "link_push.sh"), self.script_dir)
        self._write(os.path.join(self.script_dir, "parse.sh"),
                    'parse_argocd() { cat "$MOCK_DIR/apps.json"; }\n')
        self.fixture("apps.json", APPS)
        self._stub("lunar", """\
            #!/bin/sh
            printf 'ARGS: %s\\n' "$*" >> "$CAPTURE"
            case "$1 $2" in
              "sql connection-string") echo "postgres://stub"; exit 0 ;;
              "component get-json")
                for a in "$@"; do
                  [ "$a" = "--git-sha" ] && { cat "$MOCK_DIR/pinned.json"; exit 0; }
                done
                cat "$MOCK_DIR/unpinned.json"; exit 0 ;;
            esac
            cat > /dev/null
            """)
        # The last argument is the SQL. Only the annotation lookup resolves.
        self._stub("psql", """\
            #!/bin/sh
            for a in "$@"; do sql="$a"; done
            case "$sql" in
              *"count(*)"*) echo 1 ;;
              *"component_id = '%s'"*) printf '%%s\\t%%s\\n' "%s" "%s" ;;
            esac
            """ % (TARGET, TARGET, TSHA))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, path, body):
        with open(path, "w") as f:
            f.write(body)

    def _stub(self, name, body):
        path = os.path.join(self.bin, name)
        self._write(path, textwrap.dedent(body))
        os.chmod(path, 0o755)

    def fixture(self, name, content):
        self._write(os.path.join(self.mock, name), content)

    def run_script(self):
        env = {
            "PATH": self.bin + ":" + os.environ["PATH"],
            "MOCK_DIR": self.mock,
            "CAPTURE": self.capture,
            "LUNAR_COMPONENT_ID": SELF,
        }
        result = subprocess.run(
            ["bash", os.path.join(self.script_dir, "link_push.sh")],
            env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        )
        with open(self.capture) as f:
            return result, f.read()

    def test_skips_when_the_target_already_carries_the_push_at_its_sha(self):
        # The pinned read sees the prior push; the unpinned copy hasn't caught
        # up. Fails if the guard reads without --git-sha.
        self.fixture("pinned.json", PRIOR_PUSH)
        self.fixture("unpinned.json", "{}")
        result, log = self.run_script()
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("--component " + TARGET, log)
        self.assertIn("skipping (idempotent)", result.stderr)
        self.assertIn("component get-json %s --git-sha %s" % (TARGET, TSHA), log)

    def test_pushes_when_the_target_lacks_the_app_set(self):
        self.fixture("pinned.json", "{}")
        self.fixture("unpinned.json", "{}")
        result, log = self.run_script()
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("--component %s --sha %s" % (TARGET, TSHA), log)
        self.assertIn("pushed deployment posture to 1 source component(s)", result.stderr)


if __name__ == "__main__":
    unittest.main()
