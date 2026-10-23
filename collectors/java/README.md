# Java Collector

Collects Java project information, CI/CD commands, dependencies, test results, and test coverage.

## Overview

This collector gathers metadata about Java projects including build tool detection (Maven/Gradle), dependency graphs, CI/CD command tracking, test scope, JUnit test results, and JaCoCo coverage metrics. It supports Maven, Gradle, and sbt build systems (the sbt sub-collector covers Java-only sbt repos and sits alongside the scala collector for mixed Scala/Java). Code hooks analyze project structure statically, while CI hooks observe build and test commands at runtime.

**Note:** The CI-hook collectors (`test-results`, `test-coverage`, `test-scope`, `cicd`, `maven-cicd`, `gradle-cicd`, `sbt-cicd`) don't run builds or tests—they observe and collect data from commands that your CI pipeline already runs.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.java` | object | Java project metadata (version, build systems, file existence) |
| `.lang.java.dependencies` | object | Direct dependencies from pom.xml or gradle.lockfile |
| `.lang.java.cicd` | object | Java runtime CI/CD command tracking with version |
| `.lang.java.maven.cicd` | object | Maven CI/CD command tracking with version |
| `.lang.java.gradle.cicd` | object | Gradle CI/CD command tracking with version |
| `.lang.java.sbt.cicd` | object | sbt CI/CD command tracking with version |
| `.lang.java.tests` | object | Test scope, JUnit test results, and JaCoCo coverage information |
| `.testing.results` | object | Normalized test totals: `total`, `passed`, `failed`, `skipped` (dual-write from JUnit XML) |
| `.testing.all_passing` | boolean | `false` if any test failed or errored |
| `.testing.runs` | array | One entry per build (CI run, attempt, job, step, totals, `all_passing`) |
| `.testing.coverage` | object | Normalized cross-language coverage (dual-write from JaCoCo) |
| `.testing.source` | object | Normalized testing indicator |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Detects Java project structure, build tools, Java version, wrappers |
| `dependencies` | code | Extracts dependencies from pom.xml or gradle.lockfile |
| `cicd` | ci-before-command | Tracks java/javac commands in CI with version |
| `maven-cicd` | ci-before-command | Tracks Maven commands in CI with version |
| `gradle-cicd` | ci-before-command | Tracks Gradle commands in CI with version |
| `sbt-cicd` | ci-before-command | Tracks sbt commands in CI with version |
| `test-scope` | ci-before-command | Determines test scope (all vs module) |
| `test-coverage` | ci-after-command | Extracts JaCoCo coverage from XML reports |
| `test-results` | ci-after-command | Totals passed/failed/skipped tests from Surefire, Failsafe, and Gradle JUnit XML reports |

### Test results

`test-results` runs when a Maven or Gradle build finishes. `mvn`, `mvnw`, `gradle` and `gradlew` all `exec` into the build's JVM, so the hook is on that `java` process, whose exit is the end of the build. It reads the `TEST-*.xml` files in `target/surefire-reports/` and `target/failsafe-reports/` (Maven) or `build/test-results/<task>/` (Gradle) under the build's directory, and writes nothing when there are none. If the reports can't be parsed it exits with an error rather than recording partial totals.

- It counts each `<testcase>`: a failure or error fails it, `<skipped>` skips it, and a test that passed on a Surefire rerun counts as passed.
- Gradle's test-retry plugin lists every attempt as its own test, so a test that passed on retry still counts its failed attempt. Set `reports.junitXml.mergeReruns = true` to report it the way Surefire does.
- `.testing.results` and `.testing.all_passing` hold the last build to finish at a commit. `.testing.runs` keeps every build, and `testing.passing` fails if the latest attempt of any of them failed, so a passing job can't hide a failing one.
- Reports left over from an earlier build are counted too. CI checkouts start clean by default; a reused workspace needs `mvn clean` / `gradle clean`.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/java@v1.0.0
    on: ["domain:your-domain"]  # replace with your own domain or tags
    include:
      - project        # Build tools and Java version
      - dependencies   # Maven and Gradle dependencies
      - cicd           # java and javac commands in CI
      - maven-cicd     # Maven commands in CI
      - gradle-cicd    # Gradle commands in CI
      - sbt-cicd       # sbt commands in CI
      - test-scope     # Test scope in CI
      - test-coverage  # JaCoCo coverage
      - test-results   # JUnit XML test results
```
