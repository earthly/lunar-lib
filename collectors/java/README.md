# Java Collector

Collects Java project information, CI/CD commands, dependencies, and test coverage.

## Overview

This collector gathers metadata about Java projects including build tool detection (Maven/Gradle), dependency graphs, CI/CD command tracking, test scope, and JaCoCo coverage metrics. It supports both Maven and Gradle build systems. Code hooks analyze project structure statically, while CI hooks observe build and test commands at runtime.

**Note:** The CI-hook collectors (`test-coverage`, `test-scope`, `java-cicd`, `maven-cicd`, `gradle-cicd`) don't run builds or tests—they observe and collect data from commands that your CI pipeline already runs.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.java` | object | Java project metadata (version, build systems, file existence) |
| `.lang.java.dependencies` | object | Direct dependencies from pom.xml or gradle.lockfile |
| `.lang.java.cicd` | object | CI/CD command tracking with tool and version |
| `.lang.java.tests` | object | Test scope and JaCoCo coverage information |
| `.testing.coverage` | object | Normalized cross-language coverage (dual-write from JaCoCo) |
| `.testing.source` | object | Normalized testing indicator |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Detects Java project structure, build tools, Java version, wrappers |
| `dependencies` | code | Extracts dependencies from pom.xml or gradle.lockfile |
| `java-cicd` | ci-before-command | Tracks java/javac commands in CI with version |
| `maven-cicd` | ci-before-command | Tracks Maven commands in CI with version |
| `gradle-cicd` | ci-before-command | Tracks Gradle commands in CI with version |
| `test-scope` | ci-before-command | Determines test scope (all vs module) |
| `test-coverage` | ci-after-command | Extracts JaCoCo coverage from XML reports |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/java@v1.0.0
    on: [java]  # Or use domain: ["domain:your-domain"]
    # include: [project, dependencies]  # Only include specific subcollectors
```
