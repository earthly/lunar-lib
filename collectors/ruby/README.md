# Ruby Collector

Collects Ruby project information, CI/CD commands, dependencies, and bundler-audit results.

## Overview

This collector gathers metadata about Ruby projects including Bundler configuration, dependency graphs, Ruby version detection, and CI/CD command tracking. It detects Gemfile, Gemfile.lock, .ruby-version, Rakefile, and .gemspec files. The CI-hook collectors observe and collect data from `ruby`, `bundle`, and `rake` commands that your CI pipeline already runs.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.ruby` | object | Ruby project metadata (version, build systems) |
| `.lang.ruby.version` | string | Ruby version from .ruby-version or Gemfile |
| `.lang.ruby.build_systems` | array | Build systems detected (e.g., `["bundler", "rake"]`) |
| `.lang.ruby.gemfile_exists` | boolean | Gemfile detected |
| `.lang.ruby.gemfile_lock_exists` | boolean | Gemfile.lock detected |
| `.lang.ruby.ruby_version_file_exists` | boolean | .ruby-version file detected |
| `.lang.ruby.rakefile_exists` | boolean | Rakefile detected |
| `.lang.ruby.gemspec_files` | array | List of .gemspec files found |
| `.lang.ruby.cicd` | object | CI/CD ruby command tracking with version |
| `.lang.ruby.bundler.cicd` | object | CI/CD bundle command tracking with version |
| `.lang.ruby.rake.cicd` | object | CI/CD rake command tracking with version |
| `.lang.ruby.bundler_audit` | object | Bundler-audit vulnerability results |
| `.lang.ruby.dependencies` | object | Direct and development dependencies |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Collects project structure, Ruby version, build systems, gemspec files |
| `dependencies` | code | Collects dependency graph from Gemfile and Gemfile.lock |
| `cicd` | ci-before-command | Tracks ruby commands run in CI with version info |
| `bundler-cicd` | ci-before-command | Tracks bundle commands run in CI with version info |
| `rake-cicd` | ci-before-command | Tracks rake commands run in CI with version info |
| `bundler-audit` | code | Auto-runs bundler-audit against Gemfile.lock for vulnerability detection |
| `bundler-audit-cicd` | ci-after-command | Parses bundler-audit vulnerability results from CI |

## CI Integration

The CI-hook collectors (`cicd`, `bundler-cicd`, `rake-cicd`, `bundler-audit-cicd`) require a GitHub Actions workflow that runs on a Lunar-enabled runner. Example steps:

```yaml
jobs:
  build:
    runs-on: cronos  # or your Lunar-enabled runner
    steps:
      - uses: actions/checkout@v4
      - run: bundle install
      - run: ruby --version
      - run: bundle exec rake
      - run: |
          gem install bundler-audit --no-document
          bundle audit update
          bundle audit check || true
```

Each step triggers the corresponding CI hook collector, which captures command versions and output for the Component JSON.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/ruby@main
    on: ["domain:your-domain"]  # replace with your own domain or tags
    # include: [project, dependencies]  # Only include specific subcollectors
```
