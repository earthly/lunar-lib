#!/bin/bash

# Shared helper functions for the kotlin collector

# Check if the repo contains Kotlin source files (root or subdirs).
# .lang.kotlin writes are gated on *.kt / *.kts source presence — a Gradle or
# Maven build used for Java-only code lands under .lang.java instead.
is_kotlin_project() {
    git ls-files '*.kt' '*.kts' 2>/dev/null | grep -q . && return 0
    find . \( -name '*.kt' -o -name '*.kts' \) \
        -not -path '*/node_modules/*' \
        -not -path '*/build/*' \
        -not -path '*/.gradle/*' \
        2>/dev/null | head -1 | grep -q .
}

# Check whether pom.xml declares kotlin-maven-plugin (i.e. is a Kotlin-on-Maven
# project, not a plain Java pom). Returns 0 if matched, 1 otherwise.
pom_has_kotlin_plugin() {
    [[ -f "pom.xml" ]] || return 1
    grep -qE '<artifactId>kotlin-maven-plugin</artifactId>' pom.xml 2>/dev/null
}

# Grep across the Gradle build files (Kotlin DSL + Groovy DSL) for a pattern.
# Returns 0 on first match.
gradle_grep() {
    local pattern="$1"
    [[ -f "build.gradle.kts" ]] && grep -qE "$pattern" build.gradle.kts 2>/dev/null && return 0
    [[ -f "build.gradle" ]] && grep -qE "$pattern" build.gradle 2>/dev/null && return 0
    return 1
}

# Grep across every build/manifest file we care about (Gradle DSLs, pom, and the
# version catalog). Used for framework/test-framework detection.
build_grep() {
    local pattern="$1"
    gradle_grep "$pattern" && return 0
    [[ -f "pom.xml" ]] && grep -qE "$pattern" pom.xml 2>/dev/null && return 0
    [[ -f "gradle/libs.versions.toml" ]] && grep -qE "$pattern" gradle/libs.versions.toml 2>/dev/null && return 0
    return 1
}

# Extract the Kotlin version from Gradle build files:
#   kotlin("jvm") version "1.9.22"
#   kotlin("multiplatform") version "1.9.22"
#   id("org.jetbrains.kotlin.jvm") version "1.9.22"       (Kotlin DSL)
#   id 'org.jetbrains.kotlin.jvm' version '1.9.22'         (Groovy DSL)
extract_gradle_kotlin_version() {
    local f v
    for f in build.gradle.kts build.gradle; do
        [[ -f "$f" ]] || continue
        v=$(sed -n 's/.*kotlin(\"[a-z]*\")[[:space:]]*version[[:space:]]*\"\([^\"]*\)\".*/\1/p' "$f" | head -1)
        [[ -z "$v" ]] && v=$(sed -n 's/.*id(\"org\.jetbrains\.kotlin[^\"]*\")[[:space:]]*version[[:space:]]*\"\([^\"]*\)\".*/\1/p' "$f" | head -1)
        [[ -z "$v" ]] && v=$(sed -n "s/.*id[[:space:]]*['\"]org\.jetbrains\.kotlin[^'\"]*['\"][[:space:]]*version[[:space:]]*['\"]\([^'\"]*\)['\"].*/\1/p" "$f" | head -1)
        if [[ -n "$v" ]]; then echo "$v"; return 0; fi
    done
}

# Extract the Kotlin version from the Gradle version catalog:
#   [versions]
#   kotlin = "1.9.22"
extract_catalog_kotlin_version() {
    [[ -f "gradle/libs.versions.toml" ]] || return 0
    sed -n 's/^[[:space:]]*kotlin[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' gradle/libs.versions.toml | head -1
}

# Extract <kotlin.version>X.Y.Z</kotlin.version> from pom.xml.
extract_pom_kotlin_version() {
    [[ -f "pom.xml" ]] || return 0
    sed -n 's|.*<kotlin\.version>\([^<]*\)</kotlin\.version>.*|\1|p' pom.xml | head -1
}

# Extract the Gradle version from gradle/wrapper/gradle-wrapper.properties.
extract_gradle_version() {
    [[ -f "gradle/wrapper/gradle-wrapper.properties" ]] || return 0
    grep -E '^distributionUrl=' gradle/wrapper/gradle-wrapper.properties 2>/dev/null \
        | grep -oE 'gradle-[0-9]+\.[0-9]+(\.[0-9]+)?' | sed 's/gradle-//' | head -1
}
