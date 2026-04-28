#!/bin/bash

# Shared helper functions for the scala collector

# Check if the repo contains Scala source files (root or subdirs).
# .lang.scala writes are gated on *.scala source presence — sbt or Maven
# used for Java-only code lands under .lang.java instead.
is_scala_project() {
    git ls-files '*.scala' 2>/dev/null | grep -q . && return 0
    find . -name '*.scala' \
        -not -path '*/node_modules/*' \
        -not -path '*/target/*' \
        -not -path '*/.metals/*' \
        -not -path '*/.bloop/*' \
        2>/dev/null | head -1 | grep -q .
}

# Check whether pom.xml declares scala-maven-plugin (i.e. is a Scala-on-Maven
# project, not a plain Java pom). Returns 0 if matched, 1 otherwise.
pom_has_scala_plugin() {
    [[ -f "pom.xml" ]] || return 1
    grep -qE '<artifactId>scala-maven-plugin</artifactId>' pom.xml 2>/dev/null
}

# Extract scalaVersion := "X.Y.Z" from build.sbt (first match).
extract_sbt_scala_version() {
    [[ -f "build.sbt" ]] || return 0
    sed -n 's/.*scalaVersion[[:space:]]*:=[[:space:]]*"\([^"]*\)".*/\1/p' build.sbt | head -1
}

# Extract sbt.version=X.Y.Z from project/build.properties.
extract_sbt_version() {
    [[ -f "project/build.properties" ]] || return 0
    sed -n 's/^sbt\.version=\([^[:space:]]*\).*/\1/p' project/build.properties | head -1
}

# Extract <scala.version>X.Y.Z</scala.version> (or scala.binary.version) from pom.xml.
extract_pom_scala_version() {
    [[ -f "pom.xml" ]] || return 0
    local v
    v=$(sed -n 's|.*<scala\.version>\([^<]*\)</scala\.version>.*|\1|p' pom.xml | head -1)
    if [[ -z "$v" ]]; then
        v=$(sed -n 's|.*<scala\.binary\.version>\([^<]*\)</scala\.binary\.version>.*|\1|p' pom.xml | head -1)
    fi
    echo "$v"
}

# Extract `def scalaVersion = "X.Y.Z"` from build.sc (Mill).
extract_mill_scala_version() {
    [[ -f "build.sc" ]] || return 0
    sed -n 's/.*def[[:space:]]\+scalaVersion[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' build.sc | head -1
}

# Extract Mill version from .mill-version (preferred) or build.sc header comment.
extract_mill_version() {
    if [[ -f ".mill-version" ]]; then
        head -1 .mill-version | tr -d '[:space:]'
        return
    fi
    if [[ -f "build.sc" ]]; then
        # Mill's bootstrap headers sometimes include `// mill-version: X.Y.Z` style hints.
        sed -n 's|.*mill-version:[[:space:]]*\([0-9][0-9.]*\).*|\1|p' build.sc | head -1
    fi
}
