#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_scala_project; then
    echo "No Scala source files detected, exiting"
    exit 0
fi

build_sbt_exists=false
build_properties_exists=false
build_sc_exists=false
pom_xml_exists=false
scalafmt_configured=false
lockfile_exists=false
test_directory_exists=false

[[ -f "build.sbt" ]] && build_sbt_exists=true
[[ -f "project/build.properties" ]] && build_properties_exists=true
[[ -f "build.sc" ]] && build_sc_exists=true
pom_has_scala_plugin && pom_xml_exists=true
[[ -f ".scalafmt.conf" ]] && scalafmt_configured=true
[[ -f "build.sbt.lock" ]] && lockfile_exists=true

# Test directory: plain src/test/scala or cross-version variants
# (src/test/scala-2.13, src/test/scala-3, etc.)
if [[ -d "src/test/scala" ]] || compgen -G "src/test/scala-*" >/dev/null 2>&1; then
    test_directory_exists=true
fi

# Build systems array: only include tools whose manifests exist for this repo
declare -a build_systems=()
[[ "$build_sbt_exists" == "true" ]] && build_systems+=("sbt")
[[ "$build_sc_exists" == "true" ]] && build_systems+=("mill")
[[ "$pom_xml_exists" == "true" ]] && build_systems+=("maven")
if [[ ${#build_systems[@]} -gt 0 ]]; then
    build_systems_json=$(printf '%s\n' "${build_systems[@]}" | jq -R . | jq -s .)
else
    build_systems_json="[]"
fi

# Scala compiler version: prefer sbt → mill → maven
scala_version=$(extract_sbt_scala_version)
if [[ -z "$scala_version" ]]; then
    scala_version=$(extract_mill_scala_version)
fi
if [[ -z "$scala_version" ]]; then
    scala_version=$(extract_pom_scala_version)
fi

sbt_version=$(extract_sbt_version)
mill_version=$(extract_mill_version)

# Project name / version: try build.sbt first, then pom.xml
project_name=""
project_version=""
if [[ "$build_sbt_exists" == "true" ]]; then
    project_name=$(sed -n 's/.*name[[:space:]]*:=[[:space:]]*"\([^"]*\)".*/\1/p' build.sbt | head -1)
    project_version=$(sed -n 's/.*version[[:space:]]*:=[[:space:]]*"\([^"]*\)".*/\1/p' build.sbt | head -1)
fi
if [[ -z "$project_name" && "$pom_xml_exists" == "true" ]]; then
    project_name=$(sed -n 's|.*<artifactId>\([^<]*\)</artifactId>.*|\1|p' pom.xml | head -1)
fi
if [[ -z "$project_version" && "$pom_xml_exists" == "true" ]]; then
    # First <version> in pom (project version, not parent or dep)
    project_version=$(sed -n 's|.*<version>\([^<]*\)</version>.*|\1|p' pom.xml | head -1)
fi

# Cross-build: crossScalaVersions := Seq("2.13.12", "3.3.1")
cross_versions_json="[]"
is_cross_build=false
if [[ "$build_sbt_exists" == "true" ]]; then
    # Pull a single line containing crossScalaVersions and extract every quoted token.
    cross_line=$(grep -E 'crossScalaVersions[[:space:]]*:=' build.sbt 2>/dev/null | head -1 || true)
    if [[ -n "$cross_line" ]]; then
        cross_versions_json=$(echo "$cross_line" | grep -oE '"[^"]+"' | tr -d '"' | jq -R . | jq -s .)
        n=$(jq 'length' <<<"$cross_versions_json")
        [[ "$n" -gt 1 ]] && is_cross_build=true
    fi
fi

# Test frameworks — grep build files for known artifact names.
declare -a test_frameworks=()
test_grep() {
    local pattern="$1"
    [[ "$build_sbt_exists" == "true" ]] && grep -qE "$pattern" build.sbt 2>/dev/null && return 0
    [[ "$build_sc_exists" == "true" ]] && grep -qE "$pattern" build.sc 2>/dev/null && return 0
    [[ "$pom_xml_exists" == "true" ]] && grep -qE "$pattern" pom.xml 2>/dev/null && return 0
    return 1
}
test_grep '"org\.scalatest"|scalatest_|<artifactId>scalatest' && test_frameworks+=("scalatest")
test_grep '"org\.scalameta".*"munit"|"munit"|<artifactId>munit' && test_frameworks+=("munit")
test_grep '"org\.specs2"|specs2-core|<artifactId>specs2' && test_frameworks+=("specs2")
if [[ ${#test_frameworks[@]} -gt 0 ]]; then
    test_frameworks_json=$(printf '%s\n' "${test_frameworks[@]}" | jq -R . | jq -s 'unique')
else
    test_frameworks_json="[]"
fi

# Data-engineering / runtime frameworks.
declare -a frameworks=()
test_grep '"org\.apache\.spark"|spark-core|<artifactId>spark-' && frameworks+=("spark")
test_grep '"com\.typesafe\.akka"|akka-actor|<artifactId>akka-' && frameworks+=("akka")
test_grep '"org\.typelevel".*"cats"|cats-core|<artifactId>cats-' && frameworks+=("cats")
if [[ ${#frameworks[@]} -gt 0 ]]; then
    frameworks_json=$(printf '%s\n' "${frameworks[@]}" | jq -R . | jq -s 'unique')
else
    frameworks_json="[]"
fi

# Source tool: prefer sbt > mill > maven for the source.tool tag.
source_tool="sbt"
if [[ "$build_sbt_exists" != "true" ]]; then
    if [[ "$build_sc_exists" == "true" ]]; then
        source_tool="mill"
    elif [[ "$pom_xml_exists" == "true" ]]; then
        source_tool="maven"
    fi
fi

jq -n \
    --arg scala_version "$scala_version" \
    --arg sbt_version "$sbt_version" \
    --arg mill_version "$mill_version" \
    --arg project_name "$project_name" \
    --arg project_version "$project_version" \
    --arg source_tool "$source_tool" \
    --argjson build_systems "$build_systems_json" \
    --argjson build_sbt_exists "$build_sbt_exists" \
    --argjson build_properties_exists "$build_properties_exists" \
    --argjson build_sc_exists "$build_sc_exists" \
    --argjson pom_xml_exists "$pom_xml_exists" \
    --argjson scalafmt_configured "$scalafmt_configured" \
    --argjson lockfile_exists "$lockfile_exists" \
    --argjson test_directory_exists "$test_directory_exists" \
    --argjson cross_scala_versions "$cross_versions_json" \
    --argjson is_cross_build "$is_cross_build" \
    --argjson test_frameworks "$test_frameworks_json" \
    --argjson frameworks "$frameworks_json" \
    '{
        build_systems: $build_systems,
        build_sbt_exists: $build_sbt_exists,
        build_properties_exists: $build_properties_exists,
        build_sc_exists: $build_sc_exists,
        pom_xml_exists: $pom_xml_exists,
        scalafmt_configured: $scalafmt_configured,
        lockfile_exists: $lockfile_exists,
        test_directory_exists: $test_directory_exists,
        cross_scala_versions: $cross_scala_versions,
        is_cross_build: $is_cross_build,
        test_frameworks: $test_frameworks,
        frameworks: $frameworks,
        source: {
            tool: $source_tool,
            integration: "code"
        }
    }
    | if $scala_version != "" then .version = $scala_version else . end
    | if $sbt_version != "" then .sbt_version = $sbt_version else . end
    | if $mill_version != "" then .mill_version = $mill_version else . end
    | if $project_name != "" then .project_name = $project_name else . end
    | if $project_version != "" then .project_version = $project_version else . end' |
    lunar collect -j ".lang.scala" -
