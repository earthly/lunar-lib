#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a Java project
if ! is_java_project; then
    echo "No Java project detected, exiting"
    exit 0
fi

pom_exists=false
gradle_exists=false
mvnw_exists=false
gradlew_exists=false
gradle_lock_exists=false
checkstyle_configured=false
spotbugs_configured=false

# Detect build files
if [[ -f "pom.xml" ]]; then
    pom_exists=true
fi
if [[ -f "build.gradle" ]] || [[ -f "build.gradle.kts" ]]; then
    gradle_exists=true
fi
if [[ -f "mvnw" ]]; then
    mvnw_exists=true
fi
if [[ -f "gradlew" ]]; then
    gradlew_exists=true
fi
if [[ -f "gradle.lockfile" ]]; then
    gradle_lock_exists=true
fi

# Detect static analysis tools
# Checkstyle: config file or plugin in build config
if [[ -f "checkstyle.xml" ]] || [[ -f "config/checkstyle/checkstyle.xml" ]]; then
    checkstyle_configured=true
elif [[ "$pom_exists" == true ]] && grep -q 'maven-checkstyle-plugin' pom.xml 2>/dev/null; then
    checkstyle_configured=true
elif [[ -f "build.gradle" ]] && grep -q "checkstyle" build.gradle 2>/dev/null; then
    checkstyle_configured=true
elif [[ -f "build.gradle.kts" ]] && grep -q "checkstyle" build.gradle.kts 2>/dev/null; then
    checkstyle_configured=true
fi

# SpotBugs: plugin in build config
if [[ "$pom_exists" == true ]] && grep -q 'spotbugs-maven-plugin' pom.xml 2>/dev/null; then
    spotbugs_configured=true
elif [[ -f "build.gradle" ]] && grep -q "spotbugs" build.gradle 2>/dev/null; then
    spotbugs_configured=true
elif [[ -f "build.gradle.kts" ]] && grep -q "spotbugs" build.gradle.kts 2>/dev/null; then
    spotbugs_configured=true
fi

# Determine build systems
build_systems=()
if [[ "$pom_exists" == true ]]; then
    build_systems+=("maven")
fi
if [[ "$gradle_exists" == true || "$gradlew_exists" == true ]]; then
    build_systems+=("gradle")
fi

# Extract Java version from build config (static analysis, no runtime dependency)
java_version=""
if [[ "$pom_exists" == true ]]; then
    # Try <java.version>17</java.version>
    java_version=$(grep -oE '<java\.version>[0-9]+</java\.version>' pom.xml 2>/dev/null | sed 's/<java\.version>//;s/<\/java\.version>//' | head -n1 || true)
    # Try <maven.compiler.source>17</maven.compiler.source>
    if [[ -z "$java_version" ]]; then
        java_version=$(grep -oE '<maven\.compiler\.source>[0-9]+</maven\.compiler\.source>' pom.xml 2>/dev/null | sed 's/<maven\.compiler\.source>//;s/<\/maven\.compiler\.source>//' | head -n1 || true)
    fi
    # Try <maven.compiler.release>17</maven.compiler.release>
    if [[ -z "$java_version" ]]; then
        java_version=$(grep -oE '<maven\.compiler\.release>[0-9]+</maven\.compiler\.release>' pom.xml 2>/dev/null | sed 's/<maven\.compiler\.release>//;s/<\/maven\.compiler\.release>//' | head -n1 || true)
    fi
fi
if [[ -z "$java_version" && "$gradle_exists" == true ]]; then
    gradle_file=""
    if [[ -f "build.gradle" ]]; then
        gradle_file="build.gradle"
    elif [[ -f "build.gradle.kts" ]]; then
        gradle_file="build.gradle.kts"
    fi
    if [[ -n "$gradle_file" ]]; then
        # Try sourceCompatibility = '17' or sourceCompatibility = 17
        java_version=$(grep -oE "sourceCompatibility\s*=\s*['\"]?([0-9]+)['\"]?" "$gradle_file" 2>/dev/null | grep -oE '[0-9]+' | head -n1 || true)
        # Try JavaVersion.VERSION_17
        if [[ -z "$java_version" ]]; then
            java_version=$(grep -oE "JavaVersion\.VERSION_([0-9]+)" "$gradle_file" 2>/dev/null | grep -oE '[0-9]+' | head -n1 || true)
        fi
    fi
fi

# Build and collect JSON
jq -n \
    --arg version "$java_version" \
    --argjson build_systems "$(printf '%s\n' "${build_systems[@]}" | jq -R . | jq -s .)" \
    --argjson pom_exists "$pom_exists" \
    --argjson gradle_exists "$gradle_exists" \
    --argjson mvnw_exists "$mvnw_exists" \
    --argjson gradlew_exists "$gradlew_exists" \
    --argjson gradle_lock_exists "$gradle_lock_exists" \
    --argjson checkstyle_configured "$checkstyle_configured" \
    --argjson spotbugs_configured "$spotbugs_configured" \
    '{
        build_systems: $build_systems,
        native: {
            pom_xml: { exists: $pom_exists },
            build_gradle: { exists: $gradle_exists },
            mvnw: { exists: $mvnw_exists },
            gradlew: { exists: $gradlew_exists },
            gradle_lockfile: { exists: $gradle_lock_exists },
            checkstyle_configured: $checkstyle_configured,
            spotbugs_configured: $spotbugs_configured
        },
        source: {
            tool: "java",
            integration: "code"
        }
    } | if $version != "" then .version = $version else . end' | lunar collect -j ".lang.java" -
