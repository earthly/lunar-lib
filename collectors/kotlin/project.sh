#!/bin/bash
set -e

# shellcheck source=/dev/null
source "$(dirname "$0")/helpers.sh"

# Gate on Kotlin source presence — Gradle/Maven builds for Java-only code
# belong under .lang.java, not here.
if ! is_kotlin_project; then
    echo "No Kotlin source files detected, exiting"
    exit 0
fi

build_gradle_kts_exists=false
build_gradle_exists=false
settings_gradle_exists=false
pom_xml_exists=false
version_catalog_exists=false
gradlew_exists=false
lockfile_exists=false
detekt_configured=false
ktlint_configured=false
test_directory_exists=false
is_multiplatform=false
is_android=false

[[ -f "build.gradle.kts" ]] && build_gradle_kts_exists=true
[[ -f "build.gradle" ]] && build_gradle_exists=true
{ [[ -f "settings.gradle.kts" ]] || [[ -f "settings.gradle" ]]; } && settings_gradle_exists=true
pom_has_kotlin_plugin && pom_xml_exists=true
[[ -f "gradle/libs.versions.toml" ]] && version_catalog_exists=true
[[ -f "gradlew" ]] && gradlew_exists=true
[[ -f "gradle.lockfile" ]] && lockfile_exists=true

# detekt: config file or plugin reference in a build file.
if [[ -f "detekt.yml" ]] || [[ -f "detekt.yaml" ]] || [[ -f "config/detekt/detekt.yml" ]] || [[ -f "config/detekt/detekt.yaml" ]]; then
    detekt_configured=true
elif build_grep 'detekt'; then
    detekt_configured=true
fi

# ktlint: plugin reference in a build file (org.jlleitschuh.gradle.ktlint / kotlinter).
if build_grep 'ktlint|kotlinter'; then
    ktlint_configured=true
fi

# Test directory: src/test/kotlin (JVM/Maven), Android (src/androidTest, src/test),
# or Multiplatform (src/commonTest/kotlin, src/jvmTest/kotlin, ...).
if [[ -d "src/test/kotlin" ]] || [[ -d "src/androidTest" ]] \
    || compgen -G "src/*[Tt]est/kotlin" >/dev/null 2>&1 \
    || find . -type d -name kotlin -path '*[Tt]est*' -not -path '*/build/*' 2>/dev/null | head -1 | grep -q .; then
    test_directory_exists=true
fi

# Target: multiplatform > android > jvm.
if gradle_grep 'kotlin\("multiplatform"\)|org\.jetbrains\.kotlin\.multiplatform'; then
    is_multiplatform=true
fi
if gradle_grep 'com\.android\.application|com\.android\.library' || [[ -f "AndroidManifest.xml" ]] \
    || find . -name AndroidManifest.xml -not -path '*/build/*' 2>/dev/null | head -1 | grep -q .; then
    is_android=true
fi
target="jvm"
[[ "$is_android" == "true" ]] && target="android"
[[ "$is_multiplatform" == "true" ]] && target="multiplatform"

# Build systems array: only include tools whose manifests exist for this repo.
declare -a build_systems=()
if [[ "$build_gradle_kts_exists" == "true" || "$build_gradle_exists" == "true" || "$gradlew_exists" == "true" ]]; then
    build_systems+=("gradle")
fi
[[ "$pom_xml_exists" == "true" ]] && build_systems+=("maven")
if [[ ${#build_systems[@]} -gt 0 ]]; then
    build_systems_json=$(printf '%s\n' "${build_systems[@]}" | jq -R . | jq -s .)
else
    build_systems_json="[]"
fi

# Kotlin compiler version: prefer Gradle inline → version catalog → pom.
kotlin_version=$(extract_gradle_kotlin_version)
[[ -z "$kotlin_version" ]] && kotlin_version=$(extract_catalog_kotlin_version)
[[ -z "$kotlin_version" ]] && kotlin_version=$(extract_pom_kotlin_version)

gradle_version=$(extract_gradle_version)

# Project name: settings.gradle(.kts) rootProject.name, else Maven artifactId.
project_name=""
for f in settings.gradle.kts settings.gradle; do
    [[ -f "$f" ]] || continue
    project_name=$(sed -n 's/.*rootProject\.name[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$f" | head -1)
    [[ -n "$project_name" ]] && break
done
if [[ -z "$project_name" && "$pom_xml_exists" == "true" ]]; then
    project_name=$(sed -n 's|.*<artifactId>\([^<]*\)</artifactId>.*|\1|p' pom.xml | head -1)
fi

# Project version: top-level `version = "..."` in a Gradle file, else Maven <version>.
project_version=""
for f in build.gradle.kts build.gradle; do
    [[ -f "$f" ]] || continue
    project_version=$(sed -n 's/^[[:space:]]*version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$f" | head -1)
    [[ -n "$project_version" ]] && break
done
if [[ -z "$project_version" && "$pom_xml_exists" == "true" ]]; then
    project_version=$(sed -n 's|.*<version>\([^<]*\)</version>.*|\1|p' pom.xml | head -1)
fi

# Test frameworks — grep build/manifest files for known artifact names.
declare -a test_frameworks=()
build_grep 'junit|<artifactId>junit' && test_frameworks+=("junit")
build_grep 'io\.kotest|kotest-' && test_frameworks+=("kotest")
build_grep 'io\.mockk|"mockk"|mockk-' && test_frameworks+=("mockk")
build_grep 'spek|org\.spekframework' && test_frameworks+=("spek")
if [[ ${#test_frameworks[@]} -gt 0 ]]; then
    test_frameworks_json=$(printf '%s\n' "${test_frameworks[@]}" | jq -R . | jq -s 'unique')
else
    test_frameworks_json="[]"
fi

# Frameworks — grep for common Kotlin ecosystem libraries.
declare -a frameworks=()
build_grep 'io\.ktor|ktor-' && frameworks+=("ktor")
build_grep 'org\.springframework|spring-boot' && frameworks+=("spring")
build_grep 'androidx\.compose|org\.jetbrains\.compose|compose-' && frameworks+=("compose")
build_grep 'kotlinx-coroutines|kotlinx\.coroutines' && frameworks+=("coroutines")
build_grep 'org\.jetbrains\.exposed|exposed-' && frameworks+=("exposed")
if [[ ${#frameworks[@]} -gt 0 ]]; then
    frameworks_json=$(printf '%s\n' "${frameworks[@]}" | jq -R . | jq -s 'unique')
else
    frameworks_json="[]"
fi

# Source tool: gradle if any Gradle build present, else maven.
source_tool="gradle"
if [[ "$build_gradle_kts_exists" != "true" && "$build_gradle_exists" != "true" && "$gradlew_exists" != "true" && "$pom_xml_exists" == "true" ]]; then
    source_tool="maven"
fi

jq -n \
    --arg kotlin_version "$kotlin_version" \
    --arg gradle_version "$gradle_version" \
    --arg project_name "$project_name" \
    --arg project_version "$project_version" \
    --arg target "$target" \
    --arg source_tool "$source_tool" \
    --argjson build_systems "$build_systems_json" \
    --argjson build_gradle_kts_exists "$build_gradle_kts_exists" \
    --argjson build_gradle_exists "$build_gradle_exists" \
    --argjson settings_gradle_exists "$settings_gradle_exists" \
    --argjson pom_xml_exists "$pom_xml_exists" \
    --argjson version_catalog_exists "$version_catalog_exists" \
    --argjson gradlew_exists "$gradlew_exists" \
    --argjson lockfile_exists "$lockfile_exists" \
    --argjson detekt_configured "$detekt_configured" \
    --argjson ktlint_configured "$ktlint_configured" \
    --argjson test_directory_exists "$test_directory_exists" \
    --argjson is_multiplatform "$is_multiplatform" \
    --argjson is_android "$is_android" \
    --argjson test_frameworks "$test_frameworks_json" \
    --argjson frameworks "$frameworks_json" \
    '{
        project_exists: true,
        build_systems: $build_systems,
        build_gradle_kts_exists: $build_gradle_kts_exists,
        build_gradle_exists: $build_gradle_exists,
        settings_gradle_exists: $settings_gradle_exists,
        pom_xml_exists: $pom_xml_exists,
        version_catalog_exists: $version_catalog_exists,
        gradlew_exists: $gradlew_exists,
        lockfile_exists: $lockfile_exists,
        detekt_configured: $detekt_configured,
        ktlint_configured: $ktlint_configured,
        test_directory_exists: $test_directory_exists,
        target: $target,
        is_multiplatform: $is_multiplatform,
        is_android: $is_android,
        test_frameworks: $test_frameworks,
        frameworks: $frameworks,
        source: {
            tool: $source_tool,
            integration: "code"
        }
    }
    | if $kotlin_version != "" then .version = $kotlin_version else . end
    | if $gradle_version != "" then .gradle_version = $gradle_version else . end
    | if $project_name != "" then .project_name = $project_name else . end
    | if $project_version != "" then .project_version = $project_version else . end' |
    lunar collect -j ".lang.kotlin" -
