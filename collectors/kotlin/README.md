# Kotlin Collector

Collects Kotlin project information, dependencies, CI/CD commands, and test coverage.

## Overview

This collector gathers metadata about Kotlin projects from `build.gradle.kts`, `build.gradle`, `pom.xml`, and the Gradle version catalog, plus runtime CI signals like test coverage and Kotlin-compiler command usage. All sub-collectors gate on `*.kt` / `*.kts` source presence — Groovy/Maven Java-only repos land under `.lang.java`. The CI-hook collectors (`cicd`, `test-coverage`) observe commands your pipeline already runs; they do not invoke builds or tests.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.kotlin` | object | Kotlin project metadata |
| `.lang.kotlin.version` | string | Kotlin compiler version (e.g. `"1.9.22"`) |
| `.lang.kotlin.build_systems` | array | Build systems detected (`["gradle"]`, `["maven"]`, or combinations) |
| `.lang.kotlin.build_gradle_kts_exists` | boolean | `build.gradle.kts` detected (Gradle Kotlin DSL) |
| `.lang.kotlin.build_gradle_exists` | boolean | `build.gradle` detected (Gradle Groovy DSL applying a Kotlin plugin) |
| `.lang.kotlin.settings_gradle_exists` | boolean | `settings.gradle(.kts)` detected |
| `.lang.kotlin.pom_xml_exists` | boolean | `pom.xml` with `kotlin-maven-plugin` detected |
| `.lang.kotlin.version_catalog_exists` | boolean | `gradle/libs.versions.toml` version catalog detected |
| `.lang.kotlin.gradlew_exists` | boolean | Gradle wrapper (`gradlew`) detected |
| `.lang.kotlin.lockfile_exists` | boolean | `gradle.lockfile` (Gradle dependency locking) detected |
| `.lang.kotlin.detekt_configured` | boolean | detekt config (`detekt.yml`) detected |
| `.lang.kotlin.ktlint_configured` | boolean | ktlint config (ktlint Gradle plugin or `.editorconfig`) detected |
| `.lang.kotlin.test_directory_exists` | boolean | `src/test/kotlin` (or Android/Multiplatform variant) detected |
| `.lang.kotlin.project_name` | string | Project name (Gradle `rootProject.name` or Maven `artifactId`) |
| `.lang.kotlin.project_version` | string | Project version (Gradle `version` or Maven `version`) |
| `.lang.kotlin.gradle_version` | string | Gradle version from `gradle/wrapper/gradle-wrapper.properties` |
| `.lang.kotlin.target` | string | Primary target: `"jvm"`, `"android"`, or `"multiplatform"` |
| `.lang.kotlin.is_multiplatform` | boolean | True when the Kotlin Multiplatform plugin is applied |
| `.lang.kotlin.is_android` | boolean | True when an Android Gradle plugin is applied |
| `.lang.kotlin.test_frameworks` | array | Detected test frameworks (e.g. `["junit", "kotest", "mockk"]`) |
| `.lang.kotlin.frameworks` | array | Detected frameworks from deps (e.g. `["ktor", "spring", "compose", "coroutines"]`) |
| `.lang.kotlin.cicd` | object | CI/CD command tracking with compiler version |
| `.lang.kotlin.tests` | object | Test coverage information |
| `.lang.kotlin.dependencies` | object | Direct and transitive dependencies |
| `.testing.coverage` | object | Normalized cross-language test coverage |

**Note:** When a Kotlin project is detected, `.lang.kotlin` is always created (with at minimum `source` metadata), so policies can use its existence as a signal that the component is a Kotlin project.

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Collects project structure, versions, target, framework detection, test framework detection |
| `dependencies` | code | Collects dependencies from build.gradle.kts, build.gradle, pom.xml, or the version catalog |
| `cicd` | ci-before-command | Tracks `kotlinc`/`kotlin` commands run in CI with compiler version |
| `test-coverage` | ci-after-command | Extracts coverage from Kover (or JaCoCo) XML reports |

**Note on Gradle/Maven CI commands:** `gradle`/`gradlew` and `mvn`/`mvnw` invocations are already tracked by the [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector's `gradle-cicd` / `maven-cicd` sub-collectors (they fire regardless of language), so this collector's `cicd` sub-collector focuses on direct Kotlin-compiler usage rather than duplicating that data.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/kotlin@main
    on: ["domain:your-domain"]  # replace with your own domain or tags
    # include: [project, dependencies]  # Only include specific subcollectors
```
