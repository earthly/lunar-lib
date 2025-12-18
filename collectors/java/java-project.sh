#!/bin/bash
set -e

# Check if this is actually a Java project by looking for .java files
if ! find . -name "*.java" -type f 2>/dev/null | grep -q .; then
    echo "No Java files found, exiting"
    exit 0
fi

pom_exists=false
gradle_exists=false
gradlew_exists=false
gradle_lock_exists=false

if [[ -f "pom.xml" ]]; then
  pom_exists=true
fi
if [[ -f "build.gradle" ]] || [[ -f "build.gradle.kts" ]]; then
  gradle_exists=true
fi
if [[ -f "gradlew" ]]; then
  gradlew_exists=true
fi
if [[ -f "gradle.lockfile" ]]; then
  gradle_lock_exists=true
fi

# Determine build systems (can have multiple)
build_systems=()
if [[ "$pom_exists" == true ]]; then
  build_systems+=("maven")
fi
if [[ "$gradle_exists" == true || "$gradlew_exists" == true ]]; then
  build_systems+=("gradle")
fi

# Extract Java version from build files (static analysis, no runtime dependency)
java_version=""
if [[ "$pom_exists" == true ]]; then
  # Try to extract from pom.xml: <java.version>17</java.version> or <maven.compiler.source>17</maven.compiler.source>
  java_version=$(grep -oE '<java\.version>[0-9]+</java\.version>' pom.xml 2>/dev/null | sed 's/<java\.version>//;s/<\/java\.version>//' | head -n1 || echo "")
  if [[ -z "$java_version" ]]; then
    java_version=$(grep -oE '<maven\.compiler\.source>[0-9]+</maven\.compiler\.source>' pom.xml 2>/dev/null | sed 's/<maven\.compiler\.source>//;s/<\/maven\.compiler\.source>//' | head -n1 || echo "")
  fi
elif [[ "$gradle_exists" == true ]]; then
  # Try to extract from build.gradle or build.gradle.kts
  # Look for: sourceCompatibility = '17' or sourceCompatibility = JavaVersion.VERSION_17 or java { sourceCompatibility = '17' }
  gradle_file=""
  if [[ -f "build.gradle" ]]; then
    gradle_file="build.gradle"
  elif [[ -f "build.gradle.kts" ]]; then
    gradle_file="build.gradle.kts"
  fi
  if [[ -n "$gradle_file" ]]; then
    java_version=$(grep -oE "sourceCompatibility\s*=\s*['\"]?([0-9]+)['\"]?" "$gradle_file" 2>/dev/null | grep -oE '[0-9]+' | head -n1 || echo "")
    if [[ -z "$java_version" ]]; then
      java_version=$(grep -oE "JavaVersion\.VERSION_([0-9]+)" "$gradle_file" 2>/dev/null | grep -oE '[0-9]+' | head -n1 || echo "")
    fi
  fi
fi

jq -n \
  --arg version "$java_version" \
  --argjson build_systems "$(printf '%s\n' "${build_systems[@]}" | jq -R . | jq -s .)" \
  --argjson pom_exists "$pom_exists" \
  --argjson gradle_exists "$gradle_exists" \
  --argjson gradlew_exists "$gradlew_exists" \
  --argjson gradle_lock_exists "$gradle_lock_exists" \
  '{
    version: $version,
    build_systems: $build_systems,
    native: {
      pom_xml: { exists: $pom_exists },
      build_gradle: { exists: $gradle_exists },
      gradlew: { exists: $gradlew_exists },
      gradle_lockfile: { exists: $gradle_lock_exists }
    }
  }' | lunar collect -j ".lang.java" -

