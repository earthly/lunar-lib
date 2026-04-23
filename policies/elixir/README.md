# Elixir Project Guardrails

Enforce Elixir-specific project standards including mix manifest presence, Elixir version pinning, lockfile commit, test layout, Credo/Dialyzer configuration, and umbrella detection.

## Overview

This policy validates Elixir projects against best practices for mix project layout, version pinning, dependency reproducibility, testing conventions, and static analysis. All checks skip gracefully on non-Elixir projects (i.e., `.lang.elixir` missing).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `mix-project-exists` | Validates mix.exs exists | Project lacks a mix manifest |
| `elixir-version-constraint-set` | Validates `elixir: "~> X.Y"` in mix.exs | Missing Elixir version requirement |
| `dependencies-locked` | Validates mix.lock exists | Missing dependency lockfile |
| `test-directory-exists` | Validates `test/` directory | No tests committed |
| `credo-or-dialyzer-configured` | Validates Credo or Dialyzer config | No static analysis configured |
| `umbrella-app-detected` | Reports umbrella app layout | — (informational) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.elixir` | object | [`elixir`](https://github.com/earthly/lunar-lib/tree/main/collectors/elixir) collector |
| `.lang.elixir.mix_exs_exists` | boolean | [`elixir`](https://github.com/earthly/lunar-lib/tree/main/collectors/elixir) collector |
| `.lang.elixir.mix_lock_exists` | boolean | [`elixir`](https://github.com/earthly/lunar-lib/tree/main/collectors/elixir) collector |
| `.lang.elixir.elixir_requirement` | string | [`elixir`](https://github.com/earthly/lunar-lib/tree/main/collectors/elixir) collector |
| `.lang.elixir.test_directory_exists` | boolean | [`elixir`](https://github.com/earthly/lunar-lib/tree/main/collectors/elixir) collector |
| `.lang.elixir.credo_configured` | boolean | [`elixir`](https://github.com/earthly/lunar-lib/tree/main/collectors/elixir) collector |
| `.lang.elixir.dialyzer_configured` | boolean | [`elixir`](https://github.com/earthly/lunar-lib/tree/main/collectors/elixir) collector |
| `.lang.elixir.cicd.cmds` | array | [`elixir`](https://github.com/earthly/lunar-lib/tree/main/collectors/elixir) collector (additional signal for Dialyzer — `mix dialyzer` invocations) |
| `.lang.elixir.umbrella` | object | [`elixir`](https://github.com/earthly/lunar-lib/tree/main/collectors/elixir) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/elixir@main
    on: ["domain:your-domain"]  # replace with your own domain or tags
    enforcement: report-pr
    # include: [mix-project-exists, dependencies-locked]  # Only run specific checks
```

## Examples

### Passing Example

```json
{
  "lang": {
    "elixir": {
      "mix_exs_exists": true,
      "mix_lock_exists": true,
      "elixir_requirement": "~> 1.15",
      "test_directory_exists": true,
      "credo_configured": true,
      "dialyzer_configured": false,
      "umbrella": { "is_umbrella": false }
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "elixir": {
      "mix_exs_exists": true,
      "mix_lock_exists": false,
      "elixir_requirement": "",
      "test_directory_exists": false,
      "credo_configured": false,
      "dialyzer_configured": false,
      "umbrella": { "is_umbrella": false }
    }
  }
}
```

**Failure messages:**
- `"mix.lock not found. Run 'mix deps.get' and commit mix.lock for reproducible builds."`
- `"Elixir version requirement missing in mix.exs. Add 'elixir: \"~> 1.15\"' to the project/0 block."`
- `"test/ directory not found. Create a test/ directory and add ExUnit tests."`
- `"Neither Credo (.credo.exs) nor Dialyzer detected. Add {:credo, ...} or {:dialyxir, ...} to deps for static analysis."`

## Remediation

### mix-project-exists
1. Run `mix new <project-name>` to initialize a new Elixir project
2. Ensure `mix.exs` is at the project root

### elixir-version-constraint-set
1. Open `mix.exs` and find the `project/0` function
2. Add or update `elixir: "~> 1.15"` (or desired minimum) to the keyword list
3. Example:
   ```elixir
   def project do
     [
       app: :my_app,
       version: "0.1.0",
       elixir: "~> 1.15",
       ...
     ]
   end
   ```

### dependencies-locked
1. Run `mix deps.get` to fetch dependencies
2. Commit the resulting `mix.lock` to version control
3. Ensure `mix.lock` is not in `.gitignore`

### test-directory-exists
1. Create a `test/` directory: `mkdir test`
2. Add a test helper: `touch test/test_helper.exs` with `ExUnit.start()`
3. Add at least one test file under `test/`

### credo-or-dialyzer-configured
1. Add Credo: `{:credo, "~> 1.7", only: [:dev, :test], runtime: false}` to deps
2. Run `mix credo.gen.config` to create `.credo.exs`
3. Or add Dialyzer: `{:dialyxir, "~> 1.4", only: [:dev], runtime: false}` to deps
4. Run `mix dialyzer` to generate PLTs. The policy also passes if `mix dialyzer` is observed running in CI even without a local config block — wiring it into your pipeline counts.

### umbrella-app-detected
Informational — no remediation needed. This check surfaces whether the project is structured as an umbrella app.
