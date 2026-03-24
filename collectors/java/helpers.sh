#!/bin/bash

# Shared helper functions for the java collector

# Check if the current directory is a Java project.
# Requires a build manifest — stray .java files alone are not sufficient,
# since the collector reports on build systems, dependency managers, and tooling
# that only exist when a manifest is present.
is_java_project() {
    [[ -f "pom.xml" ]] || [[ -f "build.gradle" ]] || [[ -f "build.gradle.kts" ]]
}
