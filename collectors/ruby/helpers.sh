#!/bin/bash

# Shared helper functions for the ruby collector

# Check if the repo contains a Ruby project.
# Requires Gemfile, Rakefile, .ruby-version, or a .gemspec file.
is_ruby_project() {
    [[ -f "Gemfile" ]] && return 0
    [[ -f "Rakefile" ]] && return 0
    [[ -f ".ruby-version" ]] && return 0
    git ls-files --error-unmatch '*.gemspec' >/dev/null 2>&1
}
