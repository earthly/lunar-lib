# Java Project Guardrails

Enforce Java-specific project standards including build tool wrappers, Java version requirements, Maven/Gradle version minimums, and test scope.

## Overview

This policy validates Java projects against best practices for build reproducibility and project structure. It ensures projects use build tool wrappers (mvnw/gradlew), target a minimum Java version, use recent build tool versions in CI, and run tests across all modules.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `build-tool-wrapper-exists` | Validates mvnw/gradlew exists | Missing build wrapper for reproducibility |
| `min-java-version` | Ensures minimum Java version in build config | Java version below the minimum or not comparable to it, or CI ran Java below a minimum's update |
| `min-java-version-cicd` | Ensures every Java version recorded in CI meets a minimum | CI ran a JDK below the minimum, or one whose version wasn't recorded |
| `min-java-version-base-image` | Ensures the Java base image of each Dockerfile's runtime stage meets a minimum | A runtime stage builds on a Java image whose tag names a version below the minimum |
| `min-maven-version` | Ensures minimum Maven version in CI/CD | CI Maven version too old |
| `min-gradle-version` | Ensures minimum Gradle version in CI/CD | CI Gradle version too old |
| `tests-all-modules` | Ensures tests run all modules | Tests may miss modules |

### Version comparison

`min-java-version` and `min-java-version-cicd` compare full versions, so a minimum can be a feature release (`17`), a specific update (`21.0.13.1`) or [one minimum per feature release](#minimum-per-feature-release). `21.0.5` fails a `21.0.13.1` minimum and passes a `21` one.

| Version | Compared as | Notes |
|---------|-------------|-------|
| `21`, `21.0.5`, `21.0.13.1`, `17.0.21.0.3` | Element by element | Missing trailing elements count as zero, so `21` equals `21.0.0` |
| `21.0.5+11`, `21.0.5+11-LTS` | `21.0.5` | Build numbers and vendor suffixes are ignored |
| `27-ea`, `27-ea+12` | Just before `27` | A pre-release sorts before its release and after every earlier version |
| `1.8.0_202`, `1.8.0_202-b08`, `8u202` | `8.0.202` | Java 8 and earlier; `1.8` is `8` |

Against a minimum with an update, such as `21.0.13.1`:

- **A `21` build target** can't show which Java 21 update is in use, so `min-java-version` takes the update from the Java versions the `java` collector recorded in CI. It passes when every recorded version meets the minimum and fails when one doesn't, including a command whose version wasn't recorded. If CI recorded no java or javac commands, for example because the Lunar CI/CD Tracer isn't installed, it skips. A `17` target fails without CI, and a `25` target passes.
- **A version recorded in CI** is complete, so `21` there is the 21 GA release and `21.0.13` is below `21.0.13.1`.
- **Only build files and CI are checked.** `min-java-version-cicd` sees the JDKs CI ran, not the JDK in a deployed image or on a host.
- **Gradle toolchains aren't read.** The `java` collector takes the build target from `<java.version>`, `<maven.compiler.source>`, `<maven.compiler.release>`, `sourceCompatibility` or `JavaVersion.VERSION_*`, so a project that declares only `JavaLanguageVersion.of(21)` skips `min-java-version`. `min-java-version-cicd` still checks its CI JDKs.

Anything else, such as `17.x`, `latest` or an unresolved `${java.version}`, fails as unrecognized, and so does a minimum in an unrecognized format.

### Minimum per feature release

A single minimum is one floor for every feature release: `21.0.13.1` passes any 25 or 27 build, including a vulnerable `25.0.5`. To hold each release to its own fixed update, list one minimum per feature release, separated by commas, spaces or newlines:

```yaml
with:
  min_java_version: "21.0.13.1, 25.0.5.1, 27.0.1.1"
  min_java_version_cicd: "21.0.13.1, 25.0.5.1, 27.0.1.1"
```

| Version | Result |
|---------|--------|
| `21.0.13.1`, `25.0.6`, `27.0.1.1` | Passes: meets its release's minimum |
| `21.0.13`, `25.0.5` | Fails: below its release's minimum |
| `11.0.29`, `17.0.21.1` | Fails: older than every listed release |
| `23.0.2`, `26.0.1` | Fails: no minimum is listed for its release, and a newer release is listed |
| `28`, `28.0.1` | Passes: newer than every listed release, as with a single minimum |

A bare release such as `23` accepts every update of it, so `21.0.13.1, 22, 23, 24, 25.0.5.1` requires Java 21 or newer and a fixed update only on 21 and 25.

A `21` build target takes its update from CI as described above, and every Java version recorded in CI is held to the minimum for its own release.

The check sees only the version `java -version` reports, not the vendor. Corretto, Zulu and Microsoft builds of the same update all report `21.0.13.1`, and build numbers such as `+2` are ignored. IBM Semeru reports its 21.0.13 builds as `21.0.13.0.x`, which sorts below `21.0.13.1`. To accept a vendor's own fix version, split the components that use it into a separate policy entry with `on:` and list that version there.

### Runtime base images

`min-java-version-base-image` reads the image each Dockerfile's final stage builds on, following `FROM <stage>` references, from the [`docker`](https://github.com/earthly/lunar-lib/tree/main/collectors/docker) collector. Builder stages such as `FROM maven:3.9-eclipse-temurin-21 AS build` are not the runtime and aren't checked; the JDK that builds the code is `min-java-version-cicd`'s job.

The image is checked only when it matches a Java image family: a repository pattern plus the scheme that reads the Java version from the image.

- `temurin` reads the tag, with Temurin's build number: `eclipse-temurin:21.0.5_11-jre` is 21.0.5+11.
- `version` reads a tag that starts with the version: `amazoncorretto:21.0.5-al2023` is 21.0.5.
- `chainguard` reads an `openjdk-<version>` tag: `cgr.dev/acme/jre:openjdk-21.0.5` is 21.0.5.
- `distro` reads only the major in the repository name, since the tag is an image release: `gcr.io/distroless/java21-debian12` is 21.

The built-in list (`defaults`) is `*/eclipse-temurin` (temurin), `*/amazoncorretto`, `*/openjdk` and `*/azul/zulu-openjdk*` (version), `cgr.dev/*/jre` and `cgr.dev/*/jdk` (chainguard), and `*/distroless/java*` and `*/ubi*/openjdk-*` (distro). A pattern without a registry is a Docker Hub repository, `*` matches across `/` so `*/eclipse-temurin` also covers mirrors that keep the name, and the first match wins. List your own images and renamed mirrors before `defaults`:

```yaml
with:
  min_java_version_base_image: "21.0.5"
  java_base_image_families: |
    123456789012.dkr.ecr.*.amazonaws.com/platform/java-runtime  version
    defaults
```

What a result means:

- **Fail:** the image names a Java version below the minimum, either a pinned update (`21.0.3_9-jre`) or an older release (`17-jre` against `21.0.13.1`).
- **Pass:** the version the Dockerfile names meets the minimum. That is what the Dockerfile asks for, not proof of what the built image contains.
- **Skip as unknown:** a floating or major-only tag (`21-jre`, `latest`), a distro image (`java21`), a digest with no tag, or an ARG with no default. None of these shows an update, so they never pass a minimum that needs one. A release below or above every listed minimum is still decided.
- **Skip:** no Dockerfile's runtime stage builds on a listed family, for example Java installed with `apt-get` onto `debian`.

It doesn't see what ships. ARG defaults are read as written, so a `--build-arg` override is missed; a CI build that uses `--target` picks another stage; a floating tag resolves when the image is built; and distro and Chainguard packages carry vendor backports their tags don't show. For the runtime in a released image, check the scan of that image's digest.

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
| `.lang.java.maven.cicd.cmds` | array | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.gradle.cicd.cmds` | array | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.lang.java.tests.scope` | string | [`java`](https://github.com/earthly/lunar-lib/tree/main/collectors/java) collector |
| `.containers.definitions` | array | [`docker`](https://github.com/earthly/lunar-lib/tree/main/collectors/docker) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/java@v1.0.0
    on: ["domain:your-domain"]  # replace with your own domain or tags
    enforcement: report-pr
    include:
      - build-tool-wrapper-exists
      - min-java-version
      - min-java-version-cicd
      - min-java-version-base-image
      - min-maven-version
      - min-gradle-version
      - tests-all-modules
    with:
      min_java_version: "17"
      min_java_version_cicd: "17"
      min_java_version_base_image: "17"
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
      "cicd": {
        "cmds": [{ "cmd": "java -jar app.jar", "version": "21.0.5" }]
      },
      "build_systems": ["maven"],
      "mvnw_exists": true,
      "maven": {
        "cicd": {
          "cmds": [{ "cmd": "mvn clean install", "version": "3.9.6" }]
        }
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
      "cicd": {
        "cmds": [{ "cmd": "java -jar app.jar", "version": "11.0.25" }]
      },
      "build_systems": ["maven"],
      "mvnw_exists": false
    }
  }
}
```

**Failure messages:**
- `"Missing build tool wrapper(s): mvnw (Maven wrapper)"`
- `"Java version 11 is below minimum 17. Update your build config to target Java 17 or newer."`
- `"CI ran Java that does not meet minimum 17"`
- `"Java 11.0.25 is below minimum 17 (command 'java -jar app.jar')"`

## Remediation

### build-tool-wrapper-exists
- **Maven:** Run `mvn wrapper:wrapper` to generate the Maven wrapper (mvnw)
- **Gradle:** Run `gradle wrapper` to generate the Gradle wrapper (gradlew)

### min-java-version
- **Maven:** Update `<java.version>` or `<maven.compiler.source>` in pom.xml
- **Gradle:** Update `sourceCompatibility` in build.gradle
- **Minimum with an update, such as `21.0.13.1`:** keep the build file on the feature release and run CI on a JDK at or above the minimum, with the Lunar CI/CD Tracer installed so the `java` collector records it
- **Unrecognized version:** Use a plain version such as `17`, `21.0.5` or `1.8` (see [Version comparison](#version-comparison))

### min-java-version-cicd
- Upgrade the JDK your CI runs, e.g. `java-version` in `actions/setup-java` or the build image's base, to the minimum or newer
- **No Java version recorded:** the command's `java -version` or `javac -version` printed no version line, often because the JVM failed to start
- **No listed minimum:** the JDK is on a feature release the minimum skips, such as 23 between 21 and 25; move to a listed release

### min-java-version-base-image
- Build the runtime stage on an image whose tag names an update at or above the minimum, such as `eclipse-temurin:21.0.5_11-jre`, ideally pinned by digest too
- **Unknown:** replace a floating or major-only tag with a versioned one, or list your own base image as a family
- **No listed minimum:** move the runtime to a listed feature release

### min-maven-version / min-gradle-version
- Update your CI/CD pipeline or build tool wrapper to use a newer version

### tests-all-modules
- Remove `-pl`/`--projects` flags from Maven test commands
- Remove `--tests` filters from Gradle test commands
