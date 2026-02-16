# Java Project Guardrails

Enforce Java-specific project standards including build tool wrappers, Java version requirements, Maven/Gradle version minimums, and test scope.

## Overview

This policy validates Java projects against best practices for build reproducibility and project structure. It ensures projects use build tool wrappers (mvnw/gradlew), target a minimum Java version, use recent build tool versions in CI, and run tests across all modules.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `wrapper-exists` | Validates mvnw/gradlew exists | Missing build wrapper for reproducibility |
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
| `.lang.java.native.mvnw.exists` | boolean | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.native.gradlew.exists` | boolean | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.native.maven.cicd.cmds` | array | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.native.gradle.cicd.cmds` | array | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.tests.scope` | string | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/java@v1.0.0
    on: [java]  # Or use tags like ["domain:backend"]
    enforcement: report-pr
    # include: [wrapper-exists, min-java-version]  # Only run specific checks
    with:
      min_java_version: "17"        # Minimum Java version (default: "17")
      min_maven_version: "3.9.0"    # Minimum Maven version in CI (default: "3.9.0")
      min_gradle_version: "8.0.0"   # Minimum Gradle version in CI (default: "8.0.0")
```

## Examples

### Passing Example

```json
{
  "lang": {
    "java": {
      "version": "21",
      "build_systems": ["maven"],
      "native": {
        "pom_xml": { "exists": true },
        "mvnw": { "exists": true },
        "maven": {
          "cicd": {
            "cmds": [{ "cmd": "mvn clean install", "version": "3.9.6" }]
          }
        }
      },
      "tests": {
        "scope": "all"
      }
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
      "native": {
        "pom_xml": { "exists": true },
        "mvnw": { "exists": false }
      }
    }
  }
}
```

**Failure messages:**
- `"Missing build tool wrapper(s): mvnw (Maven wrapper). Wrappers ensure reproducible builds without pre-installed tools."`
- `"Java version 11 is below minimum 17. Update your build config to target Java 17 or higher."`

## Remediation

### wrapper-exists
- **Maven:** Run `mvn wrapper:wrapper` to generate the Maven wrapper (mvnw)
- **Gradle:** Run `gradle wrapper` to generate the Gradle wrapper (gradlew)
- Commit the wrapper scripts and configuration to version control

### min-java-version
- **Maven:** Update `<java.version>` or `<maven.compiler.source>` in pom.xml
- **Gradle:** Update `sourceCompatibility` in build.gradle
- Test your code with the new Java version

### min-maven-version
- Update your CI/CD pipeline to use a newer Maven version
- Or update the Maven wrapper: `mvn wrapper:wrapper -Dmaven=3.9.6`

### min-gradle-version
- Update your CI/CD pipeline to use a newer Gradle version
- Or update the Gradle wrapper: `./gradlew wrapper --gradle-version 8.5`

### tests-all-modules
- Remove `-pl`/`--projects` flags from Maven test commands
- Remove `--tests` filters from Gradle test commands
- Run full test suite: `mvn test` or `gradle test`
