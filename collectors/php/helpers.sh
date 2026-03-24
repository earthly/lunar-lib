#!/bin/bash

# Shared helper functions for the PHP collector

# Check if the current directory is a PHP project.
# Requires composer.json — stray .php files alone are not sufficient,
# since the collector reports on Composer metadata, dependencies, and tooling.
is_php_project() {
    [[ -f "composer.json" ]]
}
