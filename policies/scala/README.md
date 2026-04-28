# Scala Project Guardrails

Enforce Scala-specific project standards including build manifest presence, version pinning, dependency locking, test layout, and scalafmt configuration.

## Overview

This policy validates Scala projects against best practices for build configuration, version pinning, dependency reproducibility, testing conventions, and code formatting. All checks skip gracefully on non-Scala projects (i.e., `.lang.scala` missing). Supports sbt, Mill, and Maven (with scala-maven-plugin) build systems.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `build-tool-manifest-exists` | Validates `build.sbt`, `build.sc`, or `pom.xml` exists | Project lacks a recognised Scala build manifest |
| `scala-version-pinned` | Validates Scala compiler version is declared | Missing `scalaVersion` declaration |
| `min-scala-version` | Validates declared Scala version meets `min_scala_version` (default `2.12`) | Scala version below the configured minimum |
| `sbt-version-set` | Validates `project/build.properties` pins sbt version | Missing or empty `sbt.version` (sbt projects only) |
| `min-sbt-version` | Validates pinned sbt version meets `min_sbt_version` (default `1.9`) | sbt version below the configured minimum (sbt projects only) |
| `dependencies-locked` | Validates lockfile is present (sbt-lock or equivalent) | No lockfile committed (informational) |
| `test-module-exists` | Validates `src/test/scala` (or cross-version variant) exists | No test sources detected |
| `scalafmt-configured` | Validates `.scalafmt.conf` is committed | scalafmt not configured (informational) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.scala` | object | [`scala`](https://github.com/earthly/lunar-lib/tree/main/collectors/scala) collector |
| `.lang.scala.build_sbt_exists` | boolean | [`scala`](https://github.com/earthly/lunar-lib/tree/main/collectors/scala) collector |
| `.lang.scala.build_sc_exists` | boolean | [`scala`](https://github.com/earthly/lunar-lib/tree/main/collectors/scala) collector |
| `.lang.scala.pom_xml_exists` | boolean | [`scala`](https://github.com/earthly/lunar-lib/tree/main/collectors/scala) collector |
| `.lang.scala.version` | string | [`scala`](https://github.com/earthly/lunar-lib/tree/main/collectors/scala) collector |
| `.lang.scala.sbt_version` | string | [`scala`](https://github.com/earthly/lunar-lib/tree/main/collectors/scala) collector |
| `.lang.scala.build_systems` | array | [`scala`](https://github.com/earthly/lunar-lib/tree/main/collectors/scala) collector |
| `.lang.scala.lockfile_exists` | boolean | [`scala`](https://github.com/earthly/lunar-lib/tree/main/collectors/scala) collector |
| `.lang.scala.test_directory_exists` | boolean | [`scala`](https://github.com/earthly/lunar-lib/tree/main/collectors/scala) collector |
| `.lang.scala.scalafmt_configured` | boolean | [`scala`](https://github.com/earthly/lunar-lib/tree/main/collectors/scala) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/scala@main
    on: ["domain:your-domain"]  # replace with your own domain or tags
    enforcement: report-pr
    # include: [build-tool-manifest-exists, scala-version-pinned]  # Only run specific checks
```

## Examples

### Passing Example

```json
{
  "lang": {
    "scala": {
      "build_sbt_exists": true,
      "build_properties_exists": true,
      "version": "2.13.12",
      "sbt_version": "1.9.7",
      "build_systems": ["sbt"],
      "lockfile_exists": true,
      "test_directory_exists": true,
      "scalafmt_configured": true
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "scala": {
      "build_sbt_exists": false,
      "build_sc_exists": false,
      "pom_xml_exists": false,
      "version": "",
      "sbt_version": "",
      "build_systems": [],
      "lockfile_exists": false,
      "test_directory_exists": false,
      "scalafmt_configured": false
    }
  }
}
```

**Failure messages:**
- `"No Scala build manifest found. Add build.sbt (sbt), build.sc (Mill), or pom.xml with scala-maven-plugin."`
- `"Scala compiler version not declared. Add 'scalaVersion := \"2.13.12\"' to build.sbt or set <scala.version> in pom.xml."`
- `"Scala version 2.11.12 is below minimum 2.12. Update scalaVersion in build.sbt."`
- `"sbt version not pinned. Create project/build.properties with 'sbt.version=1.9.7'."`
- `"sbt version 1.6.2 is below minimum 1.9. Update project/build.properties."`
- `"No dependency lockfile found. Run 'sbt lock' (with sbt-lock) or commit build.sbt.lock for reproducible builds."`
- `"No test sources found. Create src/test/scala/ and add ScalaTest, MUnit, or Specs2 tests."`
- `"scalafmt not configured. Add .scalafmt.conf at the repo root for consistent formatting."`

## Remediation

### build-tool-manifest-exists
1. For sbt: `sbt new scala/scala-seed.g8` to scaffold a new project, or create `build.sbt` at the repo root
2. For Mill: install Mill and create `build.sc` at the repo root
3. For Maven: add `pom.xml` with the `scala-maven-plugin` plugin in `<plugins>`

### scala-version-pinned
1. In `build.sbt`, add at the top: `scalaVersion := "2.13.12"` (or your target version)
2. In `build.sc` (Mill): set `def scalaVersion = "2.13.12"` on your module
3. In `pom.xml`: set `<scala.version>2.13.12</scala.version>` and use it in the scala-maven-plugin config

### min-scala-version
1. Update `scalaVersion` in `build.sbt` (or the equivalent in `build.sc` / `pom.xml`) to a version at or above `min_scala_version`
2. Run `sbt clean test` (or your equivalent) to verify the project still builds and passes tests on the new version
3. For cross-builds, ensure every entry in `crossScalaVersions` also meets the minimum

### sbt-version-set
1. Create `project/build.properties`
2. Add `sbt.version=1.9.7` (or the desired version)
3. Commit the file

### min-sbt-version
1. Update `sbt.version` in `project/build.properties` to a version at or above `min_sbt_version`
2. Run `sbt --version` locally to confirm the launcher resolves the new version
3. Re-run CI to confirm reproducibility

### dependencies-locked
1. Add the sbt-lock plugin to `project/plugins.sbt`:
   ```scala
   addSbtPlugin("software.purpledragon" % "sbt-dependency-lock" % "1.5.1")
   ```
2. Run `sbt lock` to generate `build.sbt.lock`
3. Commit `build.sbt.lock` to version control

### test-module-exists
1. Create `src/test/scala/`
2. Add a test framework dependency (ScalaTest, MUnit, or Specs2)
3. Add at least one test file under `src/test/scala/`

### scalafmt-configured
1. Add `.scalafmt.conf` at the repo root with at least:
   ```
   version = "3.7.17"
   runner.dialect = scala213
   ```
2. Add the scalafmt plugin to `project/plugins.sbt`:
   ```scala
   addSbtPlugin("org.scalameta" % "sbt-scalafmt" % "2.5.2")
   ```
3. Run `sbt scalafmtAll` to format the codebase
