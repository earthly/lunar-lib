#!/usr/bin/env python3
"""Tests for the java collector's cicd sub-collector (cicd.sh).

Each case puts a fake `java` or `javac` where the agent says the traced binary
lives. The fake prints exactly what a real Temurin JDK printed for `-version`,
on the same stream. The test then runs cicd.sh with `lunar` stubbed and reads
back the command and version it recorded.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "cicd.sh")

# `-version` output of eclipse-temurin:21-jdk and eclipse-temurin:8-jdk.
JAVA_21 = textwrap.dedent(
    """\
    openjdk version "21.0.13" 2026-10-20 LTS
    OpenJDK Runtime Environment Temurin-21.0.13+9 (build 21.0.13+9-LTS)
    OpenJDK 64-Bit Server VM Temurin-21.0.13+9 (build 21.0.13+9-LTS, mixed mode, sharing)
    """
)
JAVAC_21 = "javac 21.0.13\n"  # printed on stdout
JAVA_8 = textwrap.dedent(
    """\
    openjdk version "1.8.0_512"
    OpenJDK Runtime Environment (Temurin)(build 1.8.0_512-b09)
    OpenJDK 64-Bit Server VM (Temurin)(build 25.512-b09, mixed mode)
    """
)
JAVAC_8 = "javac 1.8.0_512\n"  # printed on stderr
# The JVM announces JAVA_TOOL_OPTIONS before anything else, e.g. when the
# -XX:-UseBASE64Intrinsics mitigation is set that way.
TOOL_OPTIONS = "Picked up JAVA_TOOL_OPTIONS: -XX:-UseBASE64Intrinsics\n"
# Java 8 has no such flag and refuses to start.
JVM_START_FAILURE = TOOL_OPTIONS + textwrap.dedent(
    """\
    Unrecognized VM option 'UseBASE64Intrinsics'
    Did you mean '(+/-)PrintIntrinsics'?
    Error: Could not create the Java Virtual Machine.
    Error: A fatal exception has occurred. Program will exit.
    """
)


class CicdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="java-cicd-")
        self.jdk_bin = os.path.join(self.tmp, "jdk", "bin")
        self.stub_bin = os.path.join(self.tmp, "stub")
        self.capture = os.path.join(self.tmp, "collect.jsonl")
        os.makedirs(self.jdk_bin)
        os.makedirs(self.stub_bin)
        stub = os.path.join(self.stub_bin, "lunar")
        with open(stub, "w") as f:
            f.write(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json, os, sys
                    with open(os.environ["CAPTURE"], "a") as f:
                        f.write(json.dumps(sys.argv[1:]) + "\\n")
                    """
                )
            )
        os.chmod(stub, 0o755)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fake_jdk_binary(self, name, output, stream="stderr", exit_code=0):
        data = os.path.join(self.tmp, f"{name}.version")
        with open(data, "w") as f:
            f.write(output)
        path = os.path.join(self.jdk_bin, name)
        redirect = " >&2" if stream == "stderr" else ""
        with open(path, "w") as f:
            f.write(f'#!/bin/bash\n[ "$1" = "-version" ] || exit 64\ncat "{data}"{redirect}\nexit {exit_code}\n')
        os.chmod(path, 0o755)

    def collect(self, argv):
        env = dict(os.environ)
        env["PATH"] = self.stub_bin + os.pathsep + env["PATH"]
        env["CAPTURE"] = self.capture
        env["LUNAR_CI_COMMAND"] = json.dumps(argv, separators=(",", ":"))
        env["LUNAR_CI_COMMAND_BIN"] = argv[0]
        env["LUNAR_CI_COMMAND_BIN_DIR"] = self.jdk_bin
        subprocess.run(["bash", SCRIPT], env=env, check=True)
        with open(self.capture) as f:
            calls = [json.loads(line) for line in f]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:3], ["collect", "-j", ".lang.java.cicd.cmds"])
        return json.loads(calls[0][3])

    def test_java(self):
        self.fake_jdk_binary("java", JAVA_21)
        self.assertEqual(
            self.collect(["java", "-jar", "app.jar"]),
            [{"cmd": "java -jar app.jar", "version": "21.0.13"}],
        )

    def test_javac(self):
        self.fake_jdk_binary("javac", JAVAC_21, stream="stdout")
        self.assertEqual(
            self.collect(["javac", "-d", "out", "Main.java"]),
            [{"cmd": "javac -d out Main.java", "version": "21.0.13"}],
        )

    def test_java_8(self):
        self.fake_jdk_binary("java", JAVA_8)
        self.assertEqual(self.collect(["java", "-version"])[0]["version"], "1.8.0_512")

    def test_javac_8(self):
        self.fake_jdk_binary("javac", JAVAC_8)
        self.assertEqual(self.collect(["javac", "Main.java"])[0]["version"], "1.8.0_512")

    def test_version_after_java_tool_options_banner(self):
        self.fake_jdk_binary("java", TOOL_OPTIONS + JAVA_21)
        self.fake_jdk_binary("javac", TOOL_OPTIONS + JAVAC_21)
        self.assertEqual(self.collect(["java", "-jar", "app.jar"])[0]["version"], "21.0.13")
        os.remove(self.capture)
        self.assertEqual(self.collect(["javac", "Main.java"])[0]["version"], "21.0.13")

    def test_unreadable_version_still_records_the_command(self):
        # No version line: the command is kept with an empty version, and the
        # min-java-version-cicd check reports it as having no version.
        self.fake_jdk_binary("java", JVM_START_FAILURE, exit_code=1)
        self.assertEqual(
            self.collect(["java", "-jar", "app.jar"]),
            [{"cmd": "java -jar app.jar", "version": ""}],
        )


if __name__ == "__main__":
    unittest.main()
