# `codecov` Collector

Detects Codecov usage and fetches coverage results from the Codecov API.

## Overview

This collector detects when Codecov runs in CI and fetches coverage results from the Codecov API. It triggers on codecov commands via the `ci-after-command` hook. The presence of the `.testing.coverage` object signals that codecov ran, and the presence of `.testing.coverage.percentage` signals that coverage data was successfully fetched.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.testing.coverage.source` | object | Source metadata (tool, integration) |
| `.testing.coverage.percentage` | number | Coverage percentage from Codecov API |
| `.testing.coverage.native.codecov` | object | Full raw API response from Codecov |

**Note:** Object presence is the signal—no explicit boolean fields are used:
- `.testing.coverage` exists → codecov ran
- `.testing.coverage.percentage` exists → upload succeeded and coverage was fetched

See the example below for the full structure.

<details>
<summary>Example Component JSON output</summary>

```json
{
  "testing": {
    "coverage": {
      "source": {
        "tool": "codecov",
        "integration": "ci"
      },
      "percentage": 85.5,
      "native": {
        "codecov": {
          "coverage": 85.5,
          "files": 42,
          "lines": 1250,
          "hits": 1068,
          "misses": 182,
          "partials": 0
        }
      }
    }
  }
}
```

</details>

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `ran` | Records that codecov ran (writes source metadata) |
| `results` | Fetches coverage results from Codecov API |

Both collectors use hook type `ci-after-command` with pattern `codecov(cli)?|bash.*codecov`.

The `results` collector:
1. Detects upload commands (`upload`, `do-upload`, `upload-process`, or commands with `-t`/`-f` flags)
2. Fetches coverage from the Codecov API
3. Writes `.testing.coverage.percentage` (normalized) and `.testing.coverage.native.codecov` (full API response)

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `use_env_token` | `false` | Use `CODECOV_TOKEN` from environment instead of Lunar secret |

## Secrets

The `results` collector requires a Codecov API token. There are two options:

1. **Lunar secret (default):** Configure `CODECOV_API_TOKEN` in your Lunar secrets
2. **Environment variable:** Set `use_env_token: "true"` to use `CODECOV_TOKEN` from the CI environment

If `use_env_token` is enabled, the collector checks `CODECOV_TOKEN` first, then falls back to the Lunar secret.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/codecov@main
    on: [backend]
    # include: [ran]  # Only record that codecov ran (no API call needed)
    # with:
    #   use_env_token: "true"  # Use CODECOV_TOKEN from CI environment
```

To fetch coverage results, configure one of the token options described above.

## Related Policies

- [`codecov`](https://github.com/earthly/lunar-lib/tree/main/policies/codecov) - Validates Codecov usage and coverage thresholds
