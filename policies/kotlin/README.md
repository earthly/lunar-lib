# Kotlin Project Guardrails

Enforce Kotlin-specific project standards including build manifest presence, version pinning, wrapper commit, dependency locking, test layout, and static-analysis configuration.

## Overview

This policy validates Kotlin projects against best practices for build configuration, version pinning, dependency reproducibility, testing conventions, and code quality. All checks skip gracefully on non-Kotlin projects (i.e., `.lang.kotlin` missing). Supports Gradle (Kotlin & Groovy DSL) and Maven (with kotlin-maven-plugin) build systems.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `build-tool-manifest-exists` | Validates `build.gradle.kts`, `build.gradle`, or `pom.xml` exists | Project lacks a recognised Kotlin build manifest |
| `kotlin-version-pinned` | Validates the Kotlin compiler version is declared | Missing Kotlin plugin/`<kotlin.version>` declaration |
| `min-kotlin-version` | Validates declared Kotlin version meets `min_kotlin_version` (default `1.8`) | Kotlin version below the configured minimum |
| `build-tool-wrapper-exists` | Validates the Gradle wrapper is committed | Missing `gradlew` (Gradle projects only) |
| `dependencies-locked` | Validates `gradle.lockfile` is present | No lockfile committed (informational) |
| `test-directory-exists` | Validates `src/test/kotlin` exists | No test sources detected |
| `linter-configured` | Validates detekt or ktlint is configured | Neither detekt nor ktlint configured (informational) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.kotlin` | object | [`kotlin`](https://github.com/earthly/lunar-lib/tree/main/collectors/kotlin) collector |
| `.lang.kotlin.build_gradle_kts_exists` | boolean | [`kotlin`](https://github.com/earthly/lunar-lib/tree/main/collectors/kotlin) collector |
| `.lang.kotlin.build_gradle_exists` | boolean | [`kotlin`](https://github.com/earthly/lunar-lib/tree/main/collectors/kotlin) collector |
| `.lang.kotlin.pom_xml_exists` | boolean | [`kotlin`](https://github.com/earthly/lunar-lib/tree/main/collectors/kotlin) collector |
| `.lang.kotlin.version` | string | [`kotlin`](https://github.com/earthly/lunar-lib/tree/main/collectors/kotlin) collector |
| `.lang.kotlin.build_systems` | array | [`kotlin`](https://github.com/earthly/lunar-lib/tree/main/collectors/kotlin) collector |
| `.lang.kotlin.gradlew_exists` | boolean | [`kotlin`](https://github.com/earthly/lunar-lib/tree/main/collectors/kotlin) collector |
| `.lang.kotlin.lockfile_exists` | boolean | [`kotlin`](https://github.com/earthly/lunar-lib/tree/main/collectors/kotlin) collector |
| `.lang.kotlin.test_directory_exists` | boolean | [`kotlin`](https://github.com/earthly/lunar-lib/tree/main/collectors/kotlin) collector |
| `.lang.kotlin.detekt_configured` | boolean | [`kotlin`](https://github.com/earthly/lunar-lib/tree/main/collectors/kotlin) collector |
| `.lang.kotlin.ktlint_configured` | boolean | [`kotlin`](https://github.com/earthly/lunar-lib/tree/main/collectors/kotlin) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/kotlin@main
    on: ["domain:your-domain"]  # replace with your own domain or tags
    enforcement: report-pr
    # include: [build-tool-manifest-exists, kotlin-version-pinned]  # Only run specific checks
```

## Examples

### Passing Example

```json
{
  "lang": {
    "kotlin": {
      "build_gradle_kts_exists": true,
      "version": "1.9.22",
      "build_systems": ["gradle"],
      "gradlew_exists": true,
      "lockfile_exists": true,
      "test_directory_exists": true,
      "detekt_configured": true,
      "ktlint_configured": false
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "kotlin": {
      "build_gradle_kts_exists": false,
      "build_gradle_exists": false,
      "pom_xml_exists": false,
      "version": "",
      "build_systems": [],
      "gradlew_exists": false,
      "lockfile_exists": false,
      "test_directory_exists": false,
      "detekt_configured": false,
      "ktlint_configured": false
    }
  }
}
```

**Failure messages:**
- `"No Kotlin build manifest found. Add build.gradle.kts (Gradle Kotlin DSL), build.gradle (Groovy DSL), or pom.xml with kotlin-maven-plugin."`
- `"Kotlin compiler version not declared. Add the Kotlin Gradle plugin with a version (e.g. kotlin(\"jvm\") version \"1.9.22\") or set <kotlin.version> in pom.xml."`
- `"Kotlin version 1.7.20 is below minimum 1.8. Update the Kotlin plugin version."`
- `"Gradle wrapper not found. Run 'gradle wrapper' and commit gradlew, gradlew.bat, and gradle/wrapper/."`
- `"No dependency lockfile found. Enable Gradle dependency locking and commit gradle.lockfile for reproducible builds."`
- `"No test sources found. Create src/test/kotlin/ and add JUnit, Kotest, or MockK tests."`
- `"No Kotlin linter configured. Add detekt (detekt.yml) or ktlint for consistent code quality."`

## Remediation

### build-tool-manifest-exists
1. For Gradle (Kotlin DSL): create `build.gradle.kts` at the repo root and apply a Kotlin plugin
2. For Gradle (Groovy DSL): create `build.gradle` applying `org.jetbrains.kotlin.jvm`
3. For Maven: add `pom.xml` with the `kotlin-maven-plugin` in `<plugins>`

### kotlin-version-pinned
1. In `build.gradle.kts`, add to the `plugins {}` block: `kotlin("jvm") version "1.9.22"` (or your target version)
2. In `build.gradle` (Groovy): `id 'org.jetbrains.kotlin.jvm' version '1.9.22'`
3. In `pom.xml`: set `<kotlin.version>1.9.22</kotlin.version>` and reference it in the kotlin-maven-plugin config

### min-kotlin-version
1. Update the Kotlin plugin version (or `<kotlin.version>`) to a version at or above `min_kotlin_version`
2. Run `./gradlew build` (or `mvn verify`) to confirm the project still compiles on the new version
3. Review the Kotlin changelog for any breaking language/stdlib changes between versions

### build-tool-wrapper-exists
1. Run `gradle wrapper --gradle-version <version>` to generate the wrapper
2. Commit `gradlew`, `gradlew.bat`, and the `gradle/wrapper/` directory
3. Use `./gradlew` in CI so the pinned version is always used

### dependencies-locked
1. Enable dependency locking in `build.gradle.kts`:
   ```kotlin
   dependencyLocking { lockAllConfigurations() }
   ```
2. Run `./gradlew dependencies --write-locks` to generate `gradle.lockfile`
3. Commit `gradle.lockfile` to version control

### test-directory-exists
1. Create `src/test/kotlin/`
2. Add a test framework dependency (JUnit 5, Kotest, or MockK)
3. Add at least one test file under `src/test/kotlin/`

### linter-configured
1. For detekt, apply the plugin in `build.gradle.kts`:
   ```kotlin
   plugins { id("io.gitlab.arturbosch.detekt") version "1.23.5" }
   ```
   and commit a `detekt.yml` config at the repo root
2. For ktlint, apply `id("org.jlleitschuh.gradle.ktlint") version "12.1.0"`
3. Run `./gradlew detekt` (or `ktlintCheck`) to verify the configuration
