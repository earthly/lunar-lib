# Scala Collector

Collects Scala project information, dependencies, CI/CD commands, and test coverage.

## Overview

This collector gathers metadata about Scala projects from `build.sbt`, `build.sc`, and `pom.xml`, plus runtime CI signals like test coverage and sbt/mill command usage. All sub-collectors gate on `*.scala` source presence — sbt/Maven Java-only repos land under `.lang.java`. The CI-hook collectors (`cicd`, `test-coverage`) observe `sbt`/`mill` commands your pipeline already runs; they do not invoke tests.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.scala` | object | Scala project metadata |
| `.lang.scala.version` | string | Scala compiler version (e.g. `"2.13.12"` or `"3.3.1"`) |
| `.lang.scala.build_systems` | array | Build systems detected (`["sbt"]`, `["mill"]`, `["maven"]`, or combinations) |
| `.lang.scala.build_sbt_exists` | boolean | `build.sbt` detected |
| `.lang.scala.build_properties_exists` | boolean | `project/build.properties` detected |
| `.lang.scala.build_sc_exists` | boolean | `build.sc` detected (Mill) |
| `.lang.scala.pom_xml_exists` | boolean | `pom.xml` with `scala-maven-plugin` detected |
| `.lang.scala.scalafmt_configured` | boolean | `.scalafmt.conf` detected |
| `.lang.scala.lockfile_exists` | boolean | `build.sbt.lock` or sbt-lock plugin output detected |
| `.lang.scala.test_directory_exists` | boolean | `src/test/scala` (or cross-version variant) detected |
| `.lang.scala.project_name` | string | Project name (`name :=` in build.sbt, or Maven `artifactId`) |
| `.lang.scala.project_version` | string | Project version (`version :=` in build.sbt, or Maven `version`) |
| `.lang.scala.sbt_version` | string | sbt version from `project/build.properties` (when sbt is the build tool) |
| `.lang.scala.mill_version` | string | Mill version from `.mill-version` or `build.sc` header (when Mill is used) |
| `.lang.scala.cross_scala_versions` | array | Versions declared via `crossScalaVersions` (empty when not a cross-build) |
| `.lang.scala.is_cross_build` | boolean | True when `crossScalaVersions` declares more than one entry |
| `.lang.scala.test_frameworks` | array | Detected test frameworks (e.g. `["scalatest", "munit", "specs2"]`) |
| `.lang.scala.frameworks` | array | Detected frameworks from deps (e.g. `["spark", "akka", "cats"]`) |
| `.lang.scala.cicd` | object | CI/CD command tracking with build tool version |
| `.lang.scala.tests` | object | Test coverage information |
| `.lang.scala.dependencies` | object | Direct and transitive dependencies |
| `.testing.coverage` | object | Normalized cross-language test coverage |

**Note:** When a Scala project is detected, `.lang.scala` is always created (with at minimum `source` metadata), so policies can use its existence as a signal that the component is a Scala project.

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Collects project structure, versions, cross-build info, framework flags, test framework detection |
| `dependencies` | code | Collects dependencies from build.sbt, build.sc, or pom.xml |
| `cicd` | ci-before-command | Tracks sbt/mill commands run in CI with build tool version |
| `test-coverage` | ci-after-command | Extracts coverage from scoverage XML reports |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/scala@main
    on: ["domain:your-domain"]  # replace with your own domain or tags
    # include: [project, dependencies]  # Only include specific subcollectors
```
