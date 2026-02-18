# Java Project Guardrails

Enforce Java-specific project standards including build tool wrappers, Java version requirements, Maven/Gradle version minimums, and test scope.

## Overview

This policy validates Java projects against best practices for build reproducibility and project structure. It ensures projects use build tool wrappers (mvnw/gradlew), target a minimum Java version, use recent build tool versions in CI, and run tests across all modules.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `build-tool-wrapper-exists` | Validates mvnw/gradlew exists | Missing build wrapper for reproducibility |
| `min-java-version` | Ensures minimum Java version in build config | Java target version too old |
| `min-maven-version` | Ensures minimum Maven version in CI/CD | CI Maven version too old |
| `min-gradle-version` | Ensures minimum Gradle version in CI/CD | CI Gradle version too old |
| `tests-all-modules` | Ensures tests run all modules | Tests may miss modules |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.java` | object | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.version` | string | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.build_systems` | array | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.mvnw_exists` | boolean | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.gradlew_exists` | boolean | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.cicd.cmds` | array | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.tests.scope` | string | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/java@v1.0.0
    on: [java]
    enforcement: report-pr
    with:
      min_java_version: "17"
      min_maven_version: "3.9.0"
      min_gradle_version: "8.0.0"
```

## Examples

### Passing Example

```json
{
  "lang": {
    "java": {
      "version": "21",
      "build_systems": ["maven"],
      "mvnw_exists": true,
      "cicd": {
        "cmds": [{ "cmd": "mvn clean install", "version": "3.9.6", "tool": "maven" }]
      },
      "tests": { "scope": "all" }
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "java": {
      "version": "11",
      "build_systems": ["maven"],
      "mvnw_exists": false
    }
  }
}
```

**Failure messages:**
- `"Missing build tool wrapper(s): mvnw (Maven wrapper)"`
- `"Java version 11 (major: 11) is below minimum 17"`

## Remediation

### build-tool-wrapper-exists
- **Maven:** Run `mvn wrapper:wrapper` to generate the Maven wrapper (mvnw)
- **Gradle:** Run `gradle wrapper` to generate the Gradle wrapper (gradlew)

### min-java-version
- **Maven:** Update `<java.version>` or `<maven.compiler.source>` in pom.xml
- **Gradle:** Update `sourceCompatibility` in build.gradle

### min-maven-version / min-gradle-version
- Update your CI/CD pipeline or build tool wrapper to use a newer version

### tests-all-modules
- Remove `-pl`/`--projects` flags from Maven test commands
- Remove `--tests` filters from Gradle test commands
