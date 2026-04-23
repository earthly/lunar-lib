#!/bin/bash
set -e

# Detects SonarQube/SonarCloud configuration in the repo — sonar-project.properties,
# sonar-maven-plugin in pom.xml, org.sonarqube Gradle plugin, or <SonarQubeEnabled>
# in a .csproj. Writes any discovered paths under .code_quality.native.sonarqube.config
# so policies can see "SonarQube is wired up" even when the api sub-collector can't
# reach the server yet.

FILES_JSON="[]"

add_file() {
    local path="$1"
    FILES_JSON="$(echo "$FILES_JSON" | jq --arg p "$path" '. + [$p]')"
}

# Read from process substitution so in-loop mutations stick (no subshell).

# sonar-project.properties — the canonical marker.
while IFS= read -r f; do
    [ -n "$f" ] && add_file "${f#./}"
done < <(find . -type f -name 'sonar-project.properties' 2>/dev/null | head -20)

# Maven: sonar-maven-plugin or sonar.projectKey referenced in pom.xml.
while IFS= read -r f; do
    [ -n "$f" ] && add_file "${f#./}"
done < <(find . -type f -name 'pom.xml' 2>/dev/null \
    | xargs -r grep -l -E 'sonar-maven-plugin|sonar\.projectKey' 2>/dev/null \
    | head -20)

# Gradle: org.sonarqube plugin referenced in build.gradle / build.gradle.kts.
while IFS= read -r f; do
    [ -n "$f" ] && add_file "${f#./}"
done < <(find . -type f \( -name 'build.gradle' -o -name 'build.gradle.kts' \) 2>/dev/null \
    | xargs -r grep -l 'org.sonarqube' 2>/dev/null \
    | head -20)

# .NET: <SonarQubeEnabled> in .csproj.
while IFS= read -r f; do
    [ -n "$f" ] && add_file "${f#./}"
done < <(find . -type f -name '*.csproj' 2>/dev/null \
    | xargs -r grep -l 'SonarQubeEnabled' 2>/dev/null \
    | head -20)

COUNT="$(echo "$FILES_JSON" | jq 'length')"
if [ "$COUNT" -eq 0 ]; then
    exit 0
fi

echo "$FILES_JSON" | jq '{files: .}' | lunar collect -j ".code_quality.native.sonarqube.config" -
