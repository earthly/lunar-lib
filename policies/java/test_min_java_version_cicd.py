"""Unit tests for min-java-version-cicd.

The check compares every Java version the java collector recorded in CI
(`.lang.java.cicd.cmds[].version`) against `min_java_version_cicd`, using the
same full-version comparison as min-java-version. It doesn't need a build file,
so components that only run Java in CI are checked too. With
`require_java_version_cicd`, a Java project that CI recorded no Java for fails
instead of skipping.
"""

import contextlib
import io
import os
import unittest

from lunar_policy import CheckStatus, Node

from min_java_version import check_min_java_version
from min_java_version_cicd import NO_EVIDENCE, check_min_java_version_cicd

VARS = ("LUNAR_VAR_min_java_version", "LUNAR_VAR_min_java_version_cicd", "LUNAR_VAR_require_java_version_cicd")
NO_COMMANDS = "No java or javac commands recorded in CI"
NO_PROJECT = "No Java project detected and no java or javac commands recorded in CI"
# What the java collector's project sub-collector (collectors/java/project.sh) writes.
# A build file at the component root sets project_exists, whatever the source language.
PROJECT = {"project_exists": True, "version": "21", "build_systems": ["maven"], "pom_xml_exists": True}
KOTLIN_GRADLE = {"project_exists": True, "build_systems": ["gradle"], "build_gradle_exists": True, "gradlew_exists": True}
# Build files only in subdirectories: services/*/pom.xml, or settings.gradle.kts + gradlew + app/build.gradle.kts.
NESTED_MAVEN = {"project_exists": False, "build_systems": [], "pom_xml_exists": False, "build_gradle_exists": False}
NESTED_GRADLE = {"project_exists": False, "build_systems": ["gradle"], "build_gradle_exists": False, "gradlew_exists": True}


def node_for(java, finished=True):
    data = {"lang": {"java": java}} if java is not None else {}
    return Node.from_component_json(data, bundle_info={"workflows_finished": finished})


def run_check(cmds, minimum=None, finished=True, java=None):
    if java is None:
        java = {"cicd": {"cmds": cmds}}
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_java_version_cicd(minimum, node=node_for(java, finished))


def outcome(check):
    """Check.status reports a skip as PASS; a skip is a SKIPPED result."""
    if any(r.result == CheckStatus.SKIPPED for r in check._results):
        return CheckStatus.SKIPPED
    return check.status


def failures(check):
    return [r.failure_message for r in check._results if r.result == CheckStatus.FAIL]


def skip_reason(check):
    return next(r.failure_message for r in check._results if r.result == CheckStatus.SKIPPED)


def cmd(cmd, version):
    return {"cmd": cmd, "version": version}


class IsolatedVars(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.pop(k, None) for k in VARS}

    def tearDown(self):
        for k, v in self._saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


class MinJavaVersionCicdTest(IsolatedVars):
    def test_every_recorded_version_at_or_above_the_minimum_passes(self):
        c = run_check(
            [cmd("java -jar app.jar", "21.0.13.1"), cmd("javac -d out Main.java", "21.0.14"), cmd("java -version", "25.0.5.1")],
            "21.0.13.1",
        )
        self.assertEqual(outcome(c), CheckStatus.PASS, failures(c))

    def test_mixed_patched_and_vulnerable_fails_only_the_vulnerable_version(self):
        c = run_check(
            [
                cmd("java -jar app.jar", "21.0.13.1"),
                cmd("javac -d out Main.java", "21.0.5"),
                cmd("java -cp out Main", "21.0.5"),
                cmd("java -jar tool.jar", "17.0.21.1"),
            ],
            "21.0.13.1",
        )
        self.assertEqual(outcome(c), CheckStatus.FAIL)
        self.assertEqual(
            failures(c),
            [
                "CI ran Java that does not meet minimum 21.0.13.1",
                "Java 21.0.5 is below minimum 21.0.13.1 (2 commands, e.g. 'javac -d out Main.java')",
                "Java 17.0.21.1 is below minimum 21.0.13.1 (command 'java -jar tool.jar')",
            ],
        )

    def test_ci_only_component_without_a_build_file_is_checked(self):
        # No pom.xml/build.gradle: the collector wrote only .lang.java.cicd.
        c = run_check([cmd("java -jar liquibase.jar update", "17.0.20.1")], "17.0.21.1")
        self.assertEqual(outcome(c), CheckStatus.FAIL)
        self.assertIn("Java 17.0.20.1 is below minimum 17.0.21.1 (command 'java -jar liquibase.jar update')", failures(c))

    def test_missing_or_empty_version_fails(self):
        for entry in [cmd("java -jar app.jar", ""), cmd("java -jar app.jar", "  "), {"cmd": "java -jar app.jar"}]:
            with self.subTest(entry=entry):
                c = run_check([entry, cmd("javac Main.java", "21.0.13.1")], "21")
                self.assertEqual(outcome(c), CheckStatus.FAIL)
                self.assertIn("No Java version recorded (command 'java -jar app.jar')", failures(c))

    def test_unrecognized_version_fails(self):
        c = run_check([cmd("java -version", "21.0.5_11")], "21")
        self.assertEqual(outcome(c), CheckStatus.FAIL)
        self.assertIn('Java version "21.0.5_11" is not a recognized version format', failures(c)[1])

    def test_java_and_javac_style_versions(self):
        # java -version reports e.g. 21.0.13 or 1.8.0_512; javac -version the same numbers.
        c = run_check([cmd("java -jar a.jar", "1.8.0_512"), cmd("javac A.java", "1.8.0_512")], "8u500")
        self.assertEqual(outcome(c), CheckStatus.PASS, failures(c))
        c = run_check([cmd("javac A.java", "1.8.0_512")], "11")
        self.assertIn("Java 1.8.0_512 is below minimum 11 (command 'javac A.java')", failures(c))

    def test_recorded_versions_are_complete(self):
        # A JDK reports its full version: "27" is the 27 GA release and 21.0.13 has no
        # patch, so both are below the minimum rather than missing an update.
        c = run_check([cmd("java -version", "27")], "27.0.1.1")
        self.assertIn("Java 27 is below minimum 27.0.1.1 (command 'java -version')", failures(c))
        c = run_check([cmd("java -jar app.jar", "21.0.13")], "21.0.13.1")
        self.assertIn("Java 21.0.13 is below minimum 21.0.13.1 (command 'java -jar app.jar')", failures(c))

    def test_unparseable_minimum_fails(self):
        c = run_check([cmd("java -version", "21.0.13.1")], "latest")
        self.assertEqual(outcome(c), CheckStatus.FAIL)
        self.assertIn('min_java_version_cicd "latest" is not a recognized version format', failures(c)[0])

    def test_default_minimum_is_17(self):
        self.assertEqual(outcome(run_check([cmd("java -version", "17.0.2")])), CheckStatus.PASS)
        self.assertEqual(outcome(run_check([cmd("java -version", "11.0.33")])), CheckStatus.FAIL)

    def test_build_target_and_ci_minimums_are_separate_inputs(self):
        os.environ["LUNAR_VAR_min_java_version"] = "21"
        os.environ["LUNAR_VAR_min_java_version_cicd"] = "21.0.13.1"
        java = {"project_exists": True, "version": "21", "cicd": {"cmds": [cmd("java -jar app.jar", "21.0.5")]}}
        with contextlib.redirect_stdout(io.StringIO()):
            build = check_min_java_version(node=node_for(java))
            ci = check_min_java_version_cicd(node=node_for(java))
        self.assertEqual(outcome(build), CheckStatus.PASS)
        self.assertEqual(outcome(ci), CheckStatus.FAIL)
        self.assertIn("Java 21.0.5 is below minimum 21.0.13.1 (command 'java -jar app.jar')", failures(ci))

    def test_same_update_minimum_on_both_inputs(self):
        # A build target of 21 can't show its update, so min-java-version takes it from CI too.
        os.environ["LUNAR_VAR_min_java_version"] = "21.0.13.1"
        os.environ["LUNAR_VAR_min_java_version_cicd"] = "21.0.13.1"
        for ci_version, expected in [("21.0.13.1", CheckStatus.PASS), ("21.0.13", CheckStatus.FAIL)]:
            with self.subTest(ci_version=ci_version):
                java = {"project_exists": True, "version": "21", "cicd": {"cmds": [cmd("java -jar app.jar", ci_version)]}}
                with contextlib.redirect_stdout(io.StringIO()):
                    build = check_min_java_version(node=node_for(java))
                    ci = check_min_java_version_cicd(node=node_for(java))
                self.assertEqual((outcome(build), outcome(ci)), (expected, expected))

    def test_skips_when_no_java_ran_in_ci(self):
        self.assertEqual(outcome(run_check(None, "17", java={"project_exists": True, "version": "21"})), CheckStatus.SKIPPED)
        self.assertEqual(outcome(run_check([], "17")), CheckStatus.SKIPPED)
        self.assertEqual(outcome(run_check(None, "17", java=None)), CheckStatus.SKIPPED)

    def test_pending_while_collection_is_running(self):
        self.assertEqual(outcome(run_check(None, "17", finished=False, java=None)), CheckStatus.PENDING)


def evaluate(java, minimum="21.0.13.1", finished=True, require="true"):
    """Run the check on .lang.java (None: no Java data at all) with require_java_version_cicd."""
    with contextlib.redirect_stdout(io.StringIO()):
        return check_min_java_version_cicd(minimum, node=node_for(java, finished), require_version=require)


class RequireJavaVersionCicdTest(IsolatedVars):
    def test_detected_project_with_nothing_recorded_fails(self):
        # No cicd data at all, or an empty list once collection has finished.
        for java in [PROJECT, {**PROJECT, "cicd": {"cmds": []}}, KOTLIN_GRADLE]:
            with self.subTest(java=java):
                c = evaluate(java)
                self.assertEqual(outcome(c), CheckStatus.FAIL)
                self.assertEqual(failures(c), [NO_EVIDENCE])

    def test_off_by_default(self):
        for require in [None, "false", " False ", ""]:
            with self.subTest(require=require):
                c = evaluate(PROJECT, require=require)
                self.assertEqual(outcome(c), CheckStatus.SKIPPED)
                self.assertEqual(skip_reason(c), NO_COMMANDS)

    def test_read_from_the_policy_input(self):
        os.environ["LUNAR_VAR_require_java_version_cicd"] = " TRUE "
        self.assertEqual(failures(evaluate(PROJECT, require=None)), [NO_EVIDENCE])
        os.environ["LUNAR_VAR_require_java_version_cicd"] = "false"
        self.assertEqual(outcome(evaluate(PROJECT, require=None)), CheckStatus.SKIPPED)

    def test_unrecognized_input_fails_when_it_matters(self):
        c = evaluate(PROJECT, require="yes")
        self.assertEqual(outcome(c), CheckStatus.FAIL)
        self.assertEqual(failures(c), ['require_java_version_cicd must be "true" or "false", got "yes"'])
        # With Java recorded the input has no effect, so it isn't read.
        c = evaluate({**PROJECT, "cicd": {"cmds": [cmd("java -jar app.jar", "21.0.13.1")]}}, require="yes")
        self.assertEqual(outcome(c), CheckStatus.PASS, failures(c))

    def test_skips_without_a_detected_project(self):
        cases = {
            "nested Maven modules": NESTED_MAVEN,
            "nested Gradle build": NESTED_GRADLE,
            # Only CI hooks ran, or the project sub-collector isn't enabled.
            "no project data": {"cicd": {"cmds": []}},
            "no Java data": None,
        }
        for name, java in cases.items():
            with self.subTest(name):
                c = evaluate(java)
                self.assertEqual(outcome(c), CheckStatus.SKIPPED)
                self.assertEqual(skip_reason(c), NO_PROJECT)

    def test_pending_until_collection_finishes(self):
        # It never fails early: until collection has finished, nothing recorded is not yet evidence of absence.
        cases = {
            "detected, nothing recorded yet": PROJECT,
            "detected, empty list recorded": {**PROJECT, "cicd": {"cmds": []}},
            "project collector not finished": {"cicd": {"cmds": []}},
            "no Java data yet": None,
        }
        for name, java in cases.items():
            with self.subTest(name):
                self.assertEqual(outcome(evaluate(java, finished=False)), CheckStatus.PENDING)

    def test_commands_without_a_project_are_checked(self):
        for java in [{}, NESTED_MAVEN, NESTED_GRADLE]:
            with self.subTest(java=java):
                c = evaluate({**java, "cicd": {"cmds": [cmd("java -jar liquibase.jar update", "21.0.13.1")]}})
                self.assertEqual(outcome(c), CheckStatus.PASS, failures(c))
                c = evaluate({**java, "cicd": {"cmds": [cmd("java -jar liquibase.jar update", "21.0.5")]}})
                self.assertEqual(
                    failures(c),
                    [
                        "CI ran Java that does not meet minimum 21.0.13.1",
                        "Java 21.0.5 is below minimum 21.0.13.1 (command 'java -jar liquibase.jar update')",
                    ],
                )

    def test_recorded_observations_on_a_detected_project(self):
        cases = [
            # Empty: a command ran but its version wasn't recorded.
            (cmd("java -jar app.jar", ""), "No Java version recorded (command 'java -jar app.jar')"),
            ({"cmd": "java -jar app.jar"}, "No Java version recorded (command 'java -jar app.jar')"),
            # Invalid.
            (cmd("java -version", "21.0.5_11"), 'Java version "21.0.5_11" is not a recognized version format'),
            # Valid, below the minimum.
            (cmd("java -jar app.jar", "21.0.5"), "Java 21.0.5 is below minimum 21.0.13.1 (command 'java -jar app.jar')"),
        ]
        for entry, problem in cases:
            with self.subTest(entry=entry):
                c = evaluate({**PROJECT, "cicd": {"cmds": [entry]}})
                self.assertEqual(outcome(c), CheckStatus.FAIL)
                self.assertTrue(failures(c)[1].startswith(problem), failures(c))
        c = evaluate({**PROJECT, "cicd": {"cmds": [cmd("java -jar app.jar", "21.0.13.1"), cmd("javac A.java", "21.0.14")]}})
        self.assertEqual(outcome(c), CheckStatus.PASS, failures(c))

    def test_kotlin_gradle_build_is_checked_by_the_jdk_gradle_ran_on(self):
        gradle = "/opt/hostedtoolcache/Java_Temurin-Hotspot_jdk/21.0.13/x64/bin/java -Dorg.gradle.appname=gradlew -jar gradle/wrapper/gradle-wrapper.jar build"
        c = evaluate({**KOTLIN_GRADLE, "cicd": {"cmds": [cmd(gradle, "21.0.13.1")]}})
        self.assertEqual(outcome(c), CheckStatus.PASS, failures(c))
        c = evaluate({**KOTLIN_GRADLE, "cicd": {"cmds": [cmd(gradle, "21.0.5")]}})
        self.assertEqual(
            failures(c),
            ["CI ran Java that does not meet minimum 21.0.13.1", f"Java 21.0.5 is below minimum 21.0.13.1 (command '{gradle}')"],
        )

    def test_per_release_minimums_still_apply(self):
        minimum = "21.0.13.1, 25.0.5.1"
        cases = [
            ("25.0.6", None),
            ("28", None),
            ("25.0.5", "Java 25.0.5 is below minimum 25.0.5.1 (command 'java -jar app.jar')"),
            ("23.0.2", "Java 23.0.2 is on feature release 23, which has no listed minimum (command 'java -jar app.jar')"),
        ]
        for version, problem in cases:
            with self.subTest(version=version):
                c = evaluate({**PROJECT, "cicd": {"cmds": [cmd("java -jar app.jar", version)]}}, minimum)
                summary = "CI ran Java that does not meet the minimum for its feature release (21.0.13.1, 25.0.5.1)"
                self.assertEqual(failures(c), [summary, problem] if problem else [])

    def test_recorded_commands_get_the_same_result_either_way(self):
        # The input only decides what happens when nothing was recorded.
        observations = [
            [cmd("java -jar app.jar", "21.0.13.1")],
            [cmd("java -jar app.jar", "21.0.5"), cmd("javac A.java", "")],
            [cmd("java -version", "latest"), {"cmd": "javac A.java"}],
            [cmd("java -jar app.jar", "23.0.2"), cmd("java -jar b.jar", "17.0.21.1")],
        ]
        for cmds in observations:
            for project in [PROJECT, {}]:
                for minimum in ["17", "21.0.13.1", "21.0.13.1, 25.0.5.1", "latest"]:
                    java = {**project, "cicd": {"cmds": cmds}}
                    on = evaluate(java, minimum, require="true")
                    off = evaluate(java, minimum, require="false")
                    self.assertEqual((outcome(on), failures(on)), (outcome(off), failures(off)), (cmds, project, minimum))


if __name__ == "__main__":
    unittest.main()
