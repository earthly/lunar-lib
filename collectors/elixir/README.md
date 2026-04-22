# Elixir Collector

Collects Elixir/Mix project information, dependencies, CI/CD commands, and test coverage.

## Overview

This collector gathers metadata about Elixir projects including mix project name/version, Elixir version requirement, OTP applications, Hex dependencies, umbrella app layout, and framework detection (Phoenix, LiveView, Ecto). It runs on both code changes (for static analysis) and CI hooks (to capture runtime metrics like test coverage and mix command usage).

**Note:** The CI-hook collectors (`test-coverage`, `cicd`) don't run tests — they observe and collect data from `mix test` / `mix coveralls` commands that your CI pipeline already runs.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.elixir` | object | Elixir project metadata |
| `.lang.elixir.version` | string | Elixir runtime version |
| `.lang.elixir.otp_version` | string | Erlang/OTP version |
| `.lang.elixir.build_systems` | array | Build systems detected (e.g., `["mix"]`) |
| `.lang.elixir.mix_exs_exists` | boolean | `mix.exs` detected |
| `.lang.elixir.mix_lock_exists` | boolean | `mix.lock` detected |
| `.lang.elixir.project_name` | string | Mix project name (from `project/0`) |
| `.lang.elixir.project_version` | string | Mix project version |
| `.lang.elixir.elixir_requirement` | string | Elixir version requirement (e.g. `"~> 1.15"`) |
| `.lang.elixir.otp_apps` | array | OTP application names (from `application/0`) |
| `.lang.elixir.test_directory_exists` | boolean | `test/` directory detected |
| `.lang.elixir.credo_configured` | boolean | `.credo.exs` detected |
| `.lang.elixir.dialyzer_configured` | boolean | Dialyzer config detected (e.g. `:dialyxir` dep or `dialyzer/0` block) |
| `.lang.elixir.formatter_configured` | boolean | `.formatter.exs` detected |
| `.lang.elixir.frameworks.phoenix` | boolean | Phoenix framework detected via `:phoenix` dep |
| `.lang.elixir.frameworks.phoenix_live_view` | boolean | LiveView detected via `:phoenix_live_view` dep |
| `.lang.elixir.frameworks.ecto` | boolean | Ecto detected via `:ecto` or `:ecto_sql` dep |
| `.lang.elixir.umbrella.is_umbrella` | boolean | Umbrella project flag |
| `.lang.elixir.umbrella.apps` | array | Umbrella member app names (from `apps/*/mix.exs`) |
| `.lang.elixir.cicd` | object | CI/CD command tracking with Elixir version |
| `.lang.elixir.tests` | object | Test coverage information |
| `.lang.elixir.dependencies` | object | Direct and transitive Hex dependencies |
| `.testing.coverage` | object | Normalized cross-language test coverage |

**Note:** When a project is detected, `.lang.elixir` is always created (with at minimum `source` metadata), so policies can use its existence as a signal the component is an Elixir project.

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Collects project structure, versions, umbrella info, framework flags |
| `dependencies` | code | Collects Hex dependencies from mix.exs and mix.lock |
| `cicd` | ci-before-command | Tracks mix commands run in CI with Elixir version |
| `test-coverage` | ci-after-command | Extracts coverage from excoveralls or `mix test --cover` |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/elixir@main
    on: ["domain:your-domain"]  # replace with your own domain or tags
    # include: [project, dependencies]  # Only include specific subcollectors
```

## Notes

- **Umbrella projects**: `project.sh` detects umbrella projects via the `apps_path` declaration in the root `mix.exs` and walks `apps/*/mix.exs` to collect member app names.
- **Framework detection**: Phoenix / LiveView / Ecto flags are derived from the `deps/0` list in `mix.exs` — so adding a dep like `{:phoenix, "~> 1.7"}` flips the corresponding boolean.
- **Skip-safe**: If no Elixir indicators are found (`mix.exs` absent), all sub-collectors exit 0 without writing data.
