#!/usr/bin/env python3
"""Tests for the docker collector's dockerfile sub-collector (main.sh).

Runs the real script on the collector image (dockerfile-json, jq, parallel)
against Dockerfiles in a temp directory, with `lunar` stubbed, and reads back
the definitions it collected.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "main.sh")

LUNAR_STUB = """\
#!/usr/bin/env python3
import json, os, sys
with open(os.environ["CAPTURE"], "a") as f:
    f.write(json.dumps({"args": sys.argv[1:], "stdin": sys.stdin.read()}) + "\\n")
"""

DOCKERFILES = {
    # Runtime stage chained through another stage; the builder is not the runtime.
    "Dockerfile": """\
        ARG JAVA_VERSION=21.0.5_11
        FROM maven:3.9-eclipse-temurin-21 AS build
        RUN mvn package
        FROM eclipse-temurin:${JAVA_VERSION}-jre AS base
        FROM base AS runtime
        COPY --from=build /app.jar /app.jar
        FROM runtime
        USER app
        """,
    "single.Dockerfile": "FROM eclipse-temurin:21-jre\n",
    "Dockerfile.builder": "FROM maven:3.9-eclipse-temurin-21 AS build\nFROM build\n",
    "Dockerfile.scratch": "FROM golang:1.23 AS build\nFROM scratch\nCOPY --from=build /app /app\n",
}


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="docker-main-")
        self.repo = os.path.join(self.tmp, "repo")
        stub_bin = os.path.join(self.tmp, "stub")
        os.makedirs(self.repo)
        os.makedirs(stub_bin)
        with open(os.path.join(stub_bin, "lunar"), "w") as f:
            f.write(LUNAR_STUB)
        os.chmod(os.path.join(stub_bin, "lunar"), 0o755)
        for name, content in DOCKERFILES.items():
            with open(os.path.join(self.repo, name), "w") as f:
                f.write(textwrap.dedent(content))
        self.capture = os.path.join(self.tmp, "collect.jsonl")
        env = dict(os.environ, PATH=stub_bin + os.pathsep + os.environ["PATH"], CAPTURE=self.capture)
        subprocess.run(["bash", SCRIPT], cwd=self.repo, env=env, check=True)
        with open(self.capture) as f:
            calls = [json.loads(line) for line in f]
        defs = next(json.loads(c["stdin"]) for c in calls if c["args"][:3] == ["collect", "-j", ".containers.definitions"])
        self.stages = {d["path"]: d["final_stage"] for d in defs}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_resolves_the_final_stage_through_stage_references(self):
        stage = self.stages["Dockerfile"]
        self.assertEqual(stage["base_name"], "runtime")
        self.assertIsNone(stage["base_image"])
        self.assertEqual(stage["resolved_base_image"], "eclipse-temurin:21.0.5_11-jre")

    def test_single_stage(self):
        stage = self.stages["single.Dockerfile"]
        self.assertEqual(stage["base_image"], "eclipse-temurin:21-jre")
        self.assertEqual(stage["resolved_base_image"], "eclipse-temurin:21-jre")

    def test_runtime_built_on_the_builder(self):
        self.assertEqual(self.stages["Dockerfile.builder"]["resolved_base_image"], "maven:3.9-eclipse-temurin-21")

    def test_scratch(self):
        self.assertIsNone(self.stages["Dockerfile.scratch"]["resolved_base_image"])


if __name__ == "__main__":
    unittest.main()
