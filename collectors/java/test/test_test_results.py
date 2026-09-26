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

    def run_collector(self, command_bin="mvn"):
        env = dict(os.environ)
        env["PATH"] = self.bin + os.pathsep + env["PATH"]
        env["CAPTURE"] = self.capture
        env["LUNAR_CI_COMMAND_BIN"] = command_bin
        proc = subprocess.run(["bash", SCRIPT], cwd=self.work, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"exit {proc.returncode}: {proc.stderr}")
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
        self.assertEqual(
            got,
            {
                ".lang.java.tests.results": {**counts, "source": {"tool": tool, "integration": "ci"}},
                ".testing.results": counts,
                ".testing.all_passing": failed == 0,
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
        self.run_collector("gradlew")
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
        self.run_collector("mvnw")
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
        self.run_collector("gradlew")
        self.assert_results(total=3, passed=2, failed=1, skipped=0, tool="gradle")

    def test_gradle_retry_with_merge_reruns_counts_the_flaky_test_as_passed(self):
        # With reports.junitXml.mergeReruns = true the failed attempt becomes a
        # <flakyFailure>, but the <testsuite> still says tests="3" failures="1".
        self.layout("gradle-retry-merged", "build/test-results/test")
        self.run_collector("gradlew")
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


if __name__ == "__main__":
    unittest.main()
