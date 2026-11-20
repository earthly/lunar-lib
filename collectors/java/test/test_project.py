#!/usr/bin/env python3
"""Tests for the java collector's project sub-collector (project.sh).

Each case writes build files into an empty directory, runs project.sh there
with `lunar` stubbed, and reads back the .lang.java object it collected.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "project.sh")

LUNAR_STUB = """\
#!/usr/bin/env python3
import json, os, sys
with open(os.environ["CAPTURE"], "a") as f:
    f.write(json.dumps({"args": sys.argv[1:], "stdin": sys.stdin.read()}) + "\\n")
"""


class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="java-project-")
        self.stub_bin = os.path.join(self.tmp, "stub")
        os.makedirs(self.stub_bin)
        stub = os.path.join(self.stub_bin, "lunar")
        with open(stub, "w") as f:
            f.write(LUNAR_STUB)
        os.chmod(stub, 0o755)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def collect(self, files):
        repo = tempfile.mkdtemp(dir=self.tmp)
        for name, content in files.items():
            with open(os.path.join(repo, name), "w") as f:
                f.write(textwrap.dedent(content))
        capture = os.path.join(repo, ".collect.jsonl")
        env = dict(os.environ)
        env["PATH"] = self.stub_bin + os.pathsep + env["PATH"]
        env["CAPTURE"] = capture
        subprocess.run(["bash", SCRIPT], cwd=repo, env=env, check=True)
        with open(capture) as f:
            calls = [json.loads(line) for line in f]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["args"], ["collect", "-j", ".lang.java", "-"])
        return json.loads(calls[0]["stdin"])

    def assert_versions(self, build_file, cases):
        for name, (content, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(self.collect({build_file: content}).get("version"), expected)

    # Gradle toolchains

    def test_groovy_toolchain(self):
        self.assert_versions("build.gradle", {
            "languageVersion =": ("""\
                java {
                    toolchain {
                        languageVersion = JavaLanguageVersion.of(21)
                    }
                }
                """, "21"),
            "languageVersion.set()": ("""\
                java {
                    toolchain {
                        languageVersion.set(JavaLanguageVersion.of(17))
                    }
                }
                """, "17"),
            "one line": ("java.toolchain.languageVersion = JavaLanguageVersion.of(11)\n", "11"),
            "string version": ("java { toolchain { languageVersion = JavaLanguageVersion.of('21') } }\n", "21"),
            "jvmToolchain()": ("kotlin {\n    jvmToolchain(17)\n}\n", "17"),
            "jvmToolchain without parentheses": ("kotlin {\n    jvmToolchain 17\n}\n", "17"),
        })

    def test_kotlin_toolchain(self):
        self.assert_versions("build.gradle.kts", {
            "languageVersion.set()": ("""\
                java {
                    toolchain {
                        languageVersion.set(JavaLanguageVersion.of(17))
                    }
                }
                """, "17"),
            # Gradle 8.2+ assignment, which `gradle init` generates.
            "languageVersion =": ("""\
                java {
                    toolchain {
                        languageVersion = JavaLanguageVersion.of(21)
                    }
                }
                """, "21"),
            "jvmToolchain()": ("kotlin {\n    jvmToolchain(21)\n}\n", "21"),
            "jvmToolchain {}": ("""\
                kotlin {
                    jvmToolchain {
                        languageVersion.set(JavaLanguageVersion.of(17))
                    }
                }
                """, "17"),
        })

    def test_toolchain_only_project(self):
        # Spring Initializr's build.gradle: the toolchain is the only Java version.
        self.assertEqual(
            self.collect({
                "build.gradle": """\
                    plugins {
                        id 'java'
                        id 'org.springframework.boot' version '3.4.1'
                    }

                    java {
                        toolchain {
                            languageVersion = JavaLanguageVersion.of(21)
                        }
                    }
                    """,
            }),
            {
                "project_exists": True,
                "build_systems": ["gradle"],
                "pom_xml_exists": False,
                "build_gradle_exists": True,
                "mvnw_exists": False,
                "gradlew_exists": False,
                "gradle_lockfile_exists": False,
                "checkstyle_configured": False,
                "spotbugs_configured": False,
                "source": {"tool": "java", "integration": "code"},
                "version": "21",
            },
        )

    def test_toolchain_version_that_is_not_a_literal(self):
        self.assert_versions("build.gradle.kts", {
            "variable": ("""\
                java {
                    toolchain {
                        languageVersion = JavaLanguageVersion.of(javaVersion) // was 17
                    }
                }
                """, None),
            "version catalog": ("kotlin {\n    jvmToolchain(libs.versions.jdk.get().toInt())\n}\n", None),
        })

    # An explicit compatibility setting is the language level Gradle compiles
    # to; the toolchain only supplies its default.

    def test_source_compatibility_wins_over_toolchain(self):
        self.assert_versions("build.gradle", {
            "sourceCompatibility": ("""\
                java {
                    toolchain {
                        languageVersion = JavaLanguageVersion.of(21)
                    }
                }

                tasks.withType(JavaCompile).configureEach {
                    sourceCompatibility = '17'
                }
                """, "17"),
        })

    def test_java_version_constant_wins_over_toolchain(self):
        self.assert_versions("build.gradle.kts", {
            "JavaVersion.VERSION_11": ("""\
                android {
                    compileOptions {
                        sourceCompatibility = JavaVersion.VERSION_11
                        targetCompatibility = JavaVersion.VERSION_11
                    }
                }

                kotlin {
                    jvmToolchain(17)
                }
                """, "11"),
        })

    def test_pom_wins_over_gradle_toolchain(self):
        version = self.collect({
            "pom.xml": "<project><properties><java.version>17</java.version></properties></project>\n",
            "build.gradle": "java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }\n",
        }).get("version")
        self.assertEqual(version, "17")

    # Declarations read before toolchain support

    def test_gradle_compatibility(self):
        self.assert_versions("build.gradle", {
            "sourceCompatibility = '17'": ("sourceCompatibility = '17'\n", "17"),
            "sourceCompatibility = 1.8": ("sourceCompatibility = 1.8\n", "1.8"),
            "JavaVersion.VERSION_1_8": ("sourceCompatibility = JavaVersion.VERSION_1_8\n", "1.8"),
        })
        self.assert_versions("build.gradle.kts", {
            "JavaVersion.VERSION_17": ("java {\n    sourceCompatibility = JavaVersion.VERSION_17\n}\n", "17"),
        })

    def test_maven_properties(self):
        self.assert_versions("pom.xml", {
            "java.version": ("<properties><java.version>17</java.version></properties>\n", "17"),
            "maven.compiler.source": ("<properties><maven.compiler.source>1.8</maven.compiler.source></properties>\n", "1.8"),
            "maven.compiler.release": ("<properties><maven.compiler.release>21</maven.compiler.release></properties>\n", "21"),
        })

    def test_no_declared_version(self):
        output = self.collect({"build.gradle": "plugins {\n    id 'java'\n}\n"})
        self.assertNotIn("version", output)
        self.assertEqual(output["build_systems"], ["gradle"])


if __name__ == "__main__":
    unittest.main()
