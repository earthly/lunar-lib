#!/usr/bin/env python3
"""Tests for the java collector's test-results sub-collector.

Every fixture under fixtures/ is a report written by a real Maven Surefire /
Failsafe 3.5.2 or Gradle 8.10.2 run of a small JUnit 5 / TestNG project, so the
expected totals below are the ones the build tools printed on the console. Each
test lays the reports out the way the build tool does, runs test-results.sh
there with `lunar` stubbed, and reads back what it collected.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "test-results.sh")
FIXTURES = os.path.join(HERE, "fixtures")

# The hook fires when the build's JVM exits. These are the shapes of the JVM
# command lines the Lunar agent traced for real Maven and Gradle wrapper builds.
LAUNCHERS = {
    "maven": [
        "/opt/java/bin/java",
        "-classpath",
        "/root/.m2/wrapper/dists/apache-maven-3.9.11/a2d47e15/boot/plexus-classworlds-2.9.0.jar",
        "-Dclassworlds.conf=/root/.m2/wrapper/dists/apache-maven-3.9.11/a2d47e15/bin/m2.conf",
        "-Dmaven.home=/root/.m2/wrapper/dists/apache-maven-3.9.11/a2d47e15",
        "-Dmaven.multiModuleProjectDirectory=/work",
        "org.codehaus.plexus.classworlds.launcher.Launcher",
        "-B",
        "verify",
    ],
    "gradle": [
        "/opt/java/bin/java",
        "-Dfile.encoding=UTF-8",
        "-Xmx64m",
        "-Xms64m",
        "-Dorg.gradle.appname=gradlew",
        "-jar",
        "/work/gradle/wrapper/gradle-wrapper.jar",
        "test",
    ],
}


# The CI context the Lunar agent exports to a command hook on GitHub Actions.
CI_CONTEXT = {
    "LUNAR_CI_PIPELINE_NAME": "CI",
    "LUNAR_CI_PIPELINE_RUN_ID": "36909154652",
    "LUNAR_CI_PIPELINE_RUN_ATTEMPT": "2",
    "LUNAR_CI_JOB_NAME": "build",
    "LUNAR_CI_STEP_INDEX": "4",
}

class TestResults(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="java-test-results-")
        self.work = os.path.join(self.tmp, "work")
        self.bin = os.path.join(self.tmp, "bin")
        self.capture = os.path.join(self.tmp, "collect.jsonl")
        os.makedirs(self.work)
        os.makedirs(self.bin)
        stub = os.path.join(self.bin, "lunar")
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

    def layout(self, fixture, dest):
        """Copy fixtures/<fixture> (subdirectories included) to <work>/<dest>."""
        shutil.copytree(os.path.join(FIXTURES, fixture), os.path.join(self.work, dest), dirs_exist_ok=True)

    def run_collector(self, tool="maven", ci=None, expect_exit=0, path=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LUNAR_CI_")}
        env["PATH"] = (path or self.bin) + os.pathsep + env["PATH"]
        env["CAPTURE"] = self.capture
        env["LUNAR_CI_COMMAND"] = json.dumps(LAUNCHERS[tool], separators=(",", ":"))
        env["LUNAR_CI_COMMAND_BIN"] = "java"
        env.update(CI_CONTEXT if ci is None else ci)
        proc = subprocess.run(["bash", SCRIPT], cwd=self.work, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, expect_exit, f"exit {proc.returncode}: {proc.stderr}")
        return proc

    def collected(self):
        """Map of collected path -> parsed JSON value, across all collect calls."""
        if not os.path.exists(self.capture):
            return {}
        out = {}
        with open(self.capture) as f:
            for line in f:
                argv = json.loads(line)
                self.assertEqual(argv[:2], ["collect", "-j"])
                pairs = argv[2:]
                for path, value in zip(pairs[::2], pairs[1::2]):
                    out[path] = json.loads(value)
        return out

    def assert_results(self, total, passed, failed, skipped, tool="maven"):
        got = self.collected()
        counts = {"total": total, "passed": passed, "failed": failed, "skipped": skipped}
        run = {"pipeline": "CI", "run_id": "36909154652", "attempt": 2, "job": "build", "step": 4}
        self.assertEqual(
            got,
            {
                ".lang.java.tests.results": {**counts, "source": {"tool": tool, "integration": "ci"}},
                ".testing.results": counts,
                ".testing.all_passing": failed == 0,
                ".testing.runs": [{**run, **counts, "all_passing": failed == 0}],
            },
        )

    def test_maven_verify_reads_surefire_and_failsafe(self):
        # mvn verify: "Tests run: 8, Failures: 1, Errors: 1, Skipped: 1" from
        # Surefire plus "Tests run: 2, Failures: 1" from Failsafe.
        # failsafe-summary.xml sits in the same directory and must be ignored.
        self.layout("surefire", "target/surefire-reports")
        self.layout("failsafe", "target/failsafe-reports")
        self.run_collector()
        self.assert_results(total=10, passed=6, failed=3, skipped=1)

    def test_gradle_reads_every_test_task(self):
        # gradle check: "8 tests completed, 2 failed, 1 skipped" (test) plus
        # "2 tests completed, 1 failed" (integrationTest). Gradle reports the
        # unexpected exception as <failure> where Surefire says <error>, so the
        # totals match the Maven run.
        self.layout("gradle-test", "build/test-results/test")
        self.layout("gradle-integrationTest", "build/test-results/integrationTest")
        self.run_collector("gradle")
        self.assert_results(total=10, passed=6, failed=3, skipped=1, tool="gradle")

    def test_all_passing(self):
        self.layout("surefire", "target/surefire-reports")
        os.remove(os.path.join(self.work, "target/surefire-reports/TEST-com.example.CalculatorTest.xml"))
        self.run_collector()
        self.assert_results(total=2, passed=2, failed=0, skipped=0)

    def test_nested_modules(self):
        # Multi-module builds keep reports per module.
        self.layout("surefire", "service-a/target/surefire-reports")
        self.layout("surefire-rerun", "service-b/target/surefire-reports")
        self.run_collector()
        self.assert_results(total=12, passed=8, failed=3, skipped=1)

    def test_only_the_build_tool_that_ran_is_read(self):
        # A job that runs both `./gradlew test` and `./mvnw test` would
        # otherwise count the same suite twice.
        self.layout("surefire", "target/surefire-reports")
        self.layout("gradle-integrationTest", "build/test-results/integrationTest")
        self.run_collector("maven")
        self.assert_results(total=8, passed=5, failed=2, skipped=1)
        os.remove(self.capture)
        self.run_collector("gradle")
        self.assert_results(total=2, passed=1, failed=1, skipped=0, tool="gradle")

    def test_rerun_counts_testcases_not_suite_totals(self):
        # rerunFailingTestsCount=2: "Tests run: 4, Failures: 0, Errors: 1,
        # Skipped: 0, Flakes: 1". Surefire rewrote FlakyTest's <testsuite> to
        # tests="1" (the rerun only), so summing suite totals would give 3.
        # The flaky test passed on retry; BrokenSetupTest failed every attempt.
        self.layout("surefire-rerun", "target/surefire-reports")
        self.run_collector()
        self.assert_results(total=4, passed=3, failed=1, skipped=0)

    def test_gradle_retry_lists_each_attempt_by_default(self):
        # org.gradle.test-retry without mergeReruns: the failed attempt and the
        # passing retry are separate testcases. Gradle printed "3 tests
        # completed, 1 failed" and BUILD SUCCESSFUL.
        self.layout("gradle-retry", "build/test-results/test")
        self.run_collector("gradle")
        self.assert_results(total=3, passed=2, failed=1, skipped=0, tool="gradle")

    def test_gradle_retry_with_merge_reruns_counts_the_flaky_test_as_passed(self):
        # With reports.junitXml.mergeReruns = true the failed attempt becomes a
        # <flakyFailure>, but the <testsuite> still says tests="3" failures="1".
        self.layout("gradle-retry-merged", "build/test-results/test")
        self.run_collector("gradle")
        self.assert_results(total=2, passed=2, failed=0, skipped=0, tool="gradle")

    def test_testng_junitreports_copy_is_not_counted_twice(self):
        # TestNG writes its own TEST-*.xml copies under junitreports/, and they
        # disagree with Surefire's (they include the disabled test).
        # Surefire printed "Tests run: 3, Failures: 1".
        self.layout("testng", "target/surefire-reports")
        self.run_collector()
        self.assert_results(total=3, passed=2, failed=1, skipped=0)

    def test_markup_in_test_output_is_ignored(self):
        # The first test prints <testsuite>/<testcase>/<failure> markup, "]]>"
        # (which splits the CDATA section) and an unclosed "<!--" to stdout.
        # Surefire printed "Tests run: 3, Failures: 1, Errors: 0, Skipped: 1".
        self.layout("surefire-stdout", "target/surefire-reports")
        self.run_collector()
        self.assert_results(total=3, passed=1, failed=1, skipped=1)

    def test_no_reports_writes_nothing(self):
        os.makedirs(os.path.join(self.work, "target/site/jacoco"))
        with open(os.path.join(self.work, "target/site/jacoco/jacoco.xml"), "w") as f:
            f.write("<report/>")
        proc = self.run_collector()
        self.assertEqual(self.collected(), {})
        self.assertIn("No JUnit XML reports found", proc.stderr)

    def test_reports_outside_report_directories_are_ignored(self):
        # A repo can carry JUnit XML as test data; only build output counts.
        self.layout("surefire", "src/test/resources/samples")
        self.layout("surefire", "node_modules/some-pkg/target/surefire-reports")
        self.run_collector()
        self.assertEqual(self.collected(), {})

    def test_reports_without_testcases_write_nothing(self):
        # Derived from a real Surefire report with its <testcase> elements removed.
        src = os.path.join(FIXTURES, "surefire", "TEST-com.example.AllPassTest.xml")
        with open(src) as f:
            xml = f.read()
        head, _, _ = xml.partition("  <testcase ")
        os.makedirs(os.path.join(self.work, "target/surefire-reports"))
        with open(os.path.join(self.work, "target/surefire-reports/TEST-com.example.Empty.xml"), "w") as f:
            f.write(head + "</testsuite>\n")
        proc = self.run_collector()
        self.assertEqual(self.collected(), {})
        self.assertIn("no test cases", proc.stderr)


    def test_run_entry_escapes_names(self):
        self.layout("surefire", "target/surefire-reports")
        os.remove(os.path.join(self.work, "target/surefire-reports/TEST-com.example.CalculatorTest.xml"))
        ci = {**CI_CONTEXT, "LUNAR_CI_PIPELINE_NAME": 'Java "CI" \\ nightly', "LUNAR_CI_JOB_NAME": "it\tsuite"}
        self.run_collector(ci=ci)
        run = self.collected()[".testing.runs"][0]
        self.assertEqual((run["pipeline"], run["job"]), ('Java "CI" \\ nightly', "it suite"))

    def test_run_entry_without_ci_context(self):
        self.layout("surefire", "target/surefire-reports")
        os.remove(os.path.join(self.work, "target/surefire-reports/TEST-com.example.CalculatorTest.xml"))
        self.run_collector(ci={})
        run = self.collected()[".testing.runs"][0]
        self.assertEqual(
            {k: run[k] for k in ("pipeline", "run_id", "attempt", "job", "step")},
            {"pipeline": "", "run_id": "", "attempt": 1, "job": "", "step": 0},
        )

    def test_run_entry_ignores_non_numeric_attempt_and_step(self):
        # Both land in the JSON unquoted, so anything but digits would break it.
        self.layout("surefire", "target/surefire-reports")
        os.remove(os.path.join(self.work, "target/surefire-reports/TEST-com.example.CalculatorTest.xml"))
        self.run_collector(ci={**CI_CONTEXT, "LUNAR_CI_PIPELINE_RUN_ATTEMPT": "2x", "LUNAR_CI_STEP_INDEX": "four"})
        run = self.collected()[".testing.runs"][0]
        self.assertEqual((run["attempt"], run["step"]), (1, 0))

    def test_reports_are_parsed_in_batches(self):
        # 450 reports takes three awk batches; every batch has to be counted.
        src = os.path.join(FIXTURES, "surefire", "TEST-com.example.AllPassTest.xml")
        dest = os.path.join(self.work, "target/surefire-reports")
        os.makedirs(dest)
        for i in range(450):
            shutil.copy(src, os.path.join(dest, f"TEST-com.example.AllPassTest{i}.xml"))
        shutil.copy(os.path.join(FIXTURES, "surefire", "TEST-com.example.CalculatorTest.xml"), dest)
        self.run_collector()
        self.assert_results(total=906, passed=903, failed=2, skipped=1)

    def test_parse_failure_is_an_error_not_a_skip(self):
        # A dead awk must not read as "no reports", or as partial totals.
        self.layout("surefire", "target/surefire-reports")
        broken = os.path.join(self.tmp, "broken-bin")
        os.makedirs(broken)
        for name in os.listdir(self.bin):
            os.symlink(os.path.join(self.bin, name), os.path.join(broken, name))
        with open(os.path.join(broken, "awk"), "w") as f:
            f.write("#!/bin/sh\necho 'awk: out of memory' >&2\nexit 2\n")
        os.chmod(os.path.join(broken, "awk"), 0o755)
        proc = self.run_collector(path=broken, expect_exit=1)
        self.assertIn("Could not parse the JUnit XML reports", proc.stderr)
        self.assertEqual(self.collected(), {})


if __name__ == "__main__":
    unittest.main()
