#!/usr/bin/env python3
"""Tests for the docker collector's hadolint sub-collector.

The regression these lock in: when a component has no Dockerfiles at all,
hadolint.sh must write *nothing*. It used to emit an empty
`.containers.lint_results`, which materialized a `.containers` object on every
component that has never built a container — object presence in the Component
JSON is the detection signal, so that one write made every Dockerfile-less repo
look like it had container data and turned the container policies green instead
of skipping them.

The mirror-image case matters just as much: when Dockerfiles *do* exist and
hadolint finds nothing, `lint_results` must still be written as an empty array.
There the empty array is real signal ("hadolint ran clean"), which is what lets
the policy tell a genuine pass apart from a check that never ran.

The `lunar` stub logs each `collect` call and its piped stdin to $CAPTURE; the
real script runs as a subprocess with a stubbed `hadolint`.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(__file__)
COLLECTOR = os.path.abspath(os.path.join(HERE, ".."))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hadolint-test-")
        self.bin = os.path.join(self.tmp, "bin")
        self.work = os.path.join(self.tmp, "work")
        os.makedirs(self.bin)
        os.makedirs(self.work)
        self.capture = os.path.join(self.tmp, "collect.log")
        self._write_stubs(hadolint_output="[]", hadolint_exit=0)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stub(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, 0o755)

    def _write_stubs(self, hadolint_output, hadolint_exit):
        # lunar stub: log the collect path and the piped payload, one record per
        # line, so a test can assert both *that* a path was written and *what*
        # was written to it.
        self._stub(
            "lunar",
            textwrap.dedent(
                """\
                #!/bin/sh
                if [ "$1" = "collect" ]; then
                  path=""
                  next=""
                  for a in "$@"; do
                    if [ "$next" = "1" ]; then path="$a"; next=""; continue; fi
                    if [ "$a" = "-j" ]; then next=1; fi
                  done
                  payload=$(cat)
                  # jq pretty-prints, so payloads span lines: frame each record.
                  printf 'COLLECT %s\\n%s\\nENDCOLLECT\\n' "$path" "$payload" >> "$CAPTURE"
                fi
                exit 0
                """
            ),
        )
        self._stub(
            "hadolint",
            textwrap.dedent(
                f"""\
                #!/bin/sh
                cat <<'HADOLINT_EOF'
                {hadolint_output}
                HADOLINT_EOF
                exit {hadolint_exit}
                """
            ),
        )

    def dockerfile(self, name="Dockerfile", content="FROM alpine:3.19.1\n"):
        with open(os.path.join(self.work, name), "w") as f:
            f.write(content)

    def run_collector(self):
        env = dict(os.environ)
        env["PATH"] = self.bin + os.pathsep + env["PATH"]
        env["CAPTURE"] = self.capture
        proc = subprocess.run(
            ["bash", os.path.join(COLLECTOR, "hadolint.sh")],
            cwd=self.work,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            proc.returncode, 0, f"collector exited {proc.returncode}: {proc.stderr}"
        )
        return proc

    def collected(self):
        """Map of collected path -> parsed JSON payload."""
        if not os.path.exists(self.capture):
            return {}
        out = {}
        path = None
        payload = []
        with open(self.capture) as f:
            for line in f:
                line = line.rstrip("\n")
                if line.startswith("COLLECT "):
                    path = line[len("COLLECT "):]
                    payload = []
                elif line == "ENDCOLLECT":
                    out[path] = json.loads("\n".join(payload))
                    path = None
                elif path is not None:
                    payload.append(line)
        return out


class TestNoDockerfiles(Base):
    def test_writes_nothing(self):
        """The whole point: no Dockerfiles means no `.containers` object."""
        self.run_collector()
        self.assertEqual(self.collected(), {})

    def test_does_not_write_empty_lint_results(self):
        self.run_collector()
        self.assertNotIn(".containers.lint_results", self.collected())

    def test_reports_why_on_stderr(self):
        proc = self.run_collector()
        self.assertIn("No Dockerfiles found", proc.stderr)


class TestCleanDockerfile(Base):
    def test_empty_lint_results_still_written(self):
        """Dockerfiles exist and hadolint found nothing — that empty array is signal."""
        self.dockerfile()
        self.run_collector()
        collected = self.collected()
        self.assertIn(".containers.lint_results", collected)
        self.assertEqual(collected[".containers.lint_results"], [])

    def test_native_report_written(self):
        self.dockerfile()
        self.run_collector()
        native = self.collected()[".containers.native.hadolint"]
        self.assertEqual(native["source"]["tool"], "hadolint")
        self.assertEqual(native["report"], [])


class TestDockerfileWithIssues(Base):
    ISSUES = json.dumps([
        {"file": "Dockerfile", "line": 1, "code": "DL3006",
         "level": "warning", "message": "Always tag the version of an image explicitly"},
        {"file": "Dockerfile", "line": 4, "code": "DL3008",
         "level": "warning", "message": "Pin versions in apt get install"},
    ])

    def setUp(self):
        super().setUp()
        # hadolint exits 1 when it finds issues; the script treats that as normal.
        self._write_stubs(hadolint_output=self.ISSUES, hadolint_exit=1)

    def test_issues_grouped_by_path(self):
        self.dockerfile()
        self.run_collector()
        results = self.collected()[".containers.lint_results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "Dockerfile")
        self.assertEqual(
            sorted(i["rule"] for i in results[0]["issues"]), ["DL3006", "DL3008"]
        )

    def test_issue_fields_normalized(self):
        self.dockerfile()
        self.run_collector()
        issue = self.collected()[".containers.lint_results"][0]["issues"][0]
        self.assertEqual(
            sorted(issue.keys()), ["line", "message", "rule", "severity"]
        )
        self.assertEqual(issue["severity"], "warning")


class TestCustomFindCommand(Base):
    def test_find_command_matching_nothing_writes_nothing(self):
        """A find_command override that matches no file is still 'no Dockerfiles'."""
        self.dockerfile()
        env_backup = os.environ.get("LUNAR_VAR_FIND_COMMAND")
        os.environ["LUNAR_VAR_FIND_COMMAND"] = "find . -name 'Containerfile'"
        try:
            self.run_collector()
        finally:
            if env_backup is None:
                os.environ.pop("LUNAR_VAR_FIND_COMMAND", None)
            else:
                os.environ["LUNAR_VAR_FIND_COMMAND"] = env_backup
        self.assertEqual(self.collected(), {})


if __name__ == "__main__":
    unittest.main()
