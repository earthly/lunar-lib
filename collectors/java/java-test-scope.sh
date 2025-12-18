#!/bin/bash

set -e

# Determine Java test scope based on the CI command.
# We inspect LUNAR_CI_COMMAND (JSON array of args) to see if tests
# are run for the whole project or limited modules.

cmd_str=$(echo "$LUNAR_CI_COMMAND" | jq -r 'join(" ")')

# Default scope is "all" tests in the project.
scope="all"

# If the command includes -pl or -projects (Maven) or --tests (Gradle) with a specific pattern,
# we treat that as a narrower/module-level scope.
if echo "$cmd_str" | grep -qE '\s(-pl|-projects)\s'; then
  scope="module"
elif echo "$cmd_str" | grep -qE '\s--tests\s'; then
  scope="module"
fi

echo "Detected Java test scope: $scope (command: $cmd_str)" >&2

# Collect scope under .lang.java.tests.run (as JSON string)
jq -n --arg scope "$scope" '$scope' | lunar collect -j ".lang.java.tests.run" -

