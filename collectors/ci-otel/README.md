# CI OpenTelemetry Collector

Emits OpenTelemetry traces for CI pipeline runs, providing detailed observability into job execution.

## Overview

This collector instruments CI pipelines with OpenTelemetry distributed tracing. It captures job, step, and command-level spans with timing and metadata, sending traces to any OTLP-compatible backend (Tempo, Jaeger, Honeycomb, etc.). This enables detailed visibility into CI performance, bottlenecks, and failures through your observability stack.

## Collected Data

This collector writes to the following Component JSON paths (when debug mode is enabled):

| Path | Type | Description |
|------|------|-------------|
| `.ci.traces.{trace_id}` | object | Trace metadata including job, steps, and commands |
| `.ci.traces.{trace_id}.steps.{step_index}` | object | Step-level timing and metadata |
| `.ci.traces.{trace_id}.steps.{step_index}.commands.{cmd_hash}` | object | Command-level timing and process info |

**Note:** The primary output is OpenTelemetry traces sent to the configured OTLP endpoint. Component JSON data is only collected when `debug: "true"` is set.

## Collectors

This plugin provides the following collectors:

| Collector | Description |
|-----------|-------------|
| `job-start` | Starts the root span for the CI job, generates trace ID from component and job ID |
| `job-end` | Ends the root span, calculates duration, sends the complete job span |
| `step-start` | Starts a span for each CI step as a child of the job span |
| `step-end` | Ends the step span, calculates duration, sends the complete step span |
| `cmd-start` | Starts a span for each CI command under the current step |
| `cmd-end` | Ends the command span with exit code and duration metadata |

## Trace Structure

A typical trace hierarchy looks like:

```
Job: github.com/acme/backend #123 abc1234 (root span)
├── Step 0: Checkout (step span)
│   ├── ["/usr/bin/git", "checkout", "--detach"]
│   └── ["/usr/bin/git", "submodule", "status"]
├── Step 1: Build (step span)
│   └── ["/usr/bin/go", "build", "./..."]
└── Step 2: Test (step span)
    └── ["/usr/bin/go", "test", "-v", "./..."]
```

## Span Attributes

All spans include:

| Attribute | Description |
|-----------|-------------|
| `lunar.component_id` | Component identifier |
| `lunar.pr` | Pull request number |
| `lunar.git_sha` | Git commit SHA |
| `lunar.domain` | Component domain |
| `lunar.owner` | Component owner |
| `ci.vendor` | CI vendor (e.g., "github-actions") |
| `ci.span_type` | Span type: "job", "step", or "command" |
| `ci.job_id` | CI job identifier |
| `ci.job_name` | CI job name |

Step and command spans include additional context-specific attributes.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/ci-otel@v1.0.0
    on: ["domain:your-domain"]
    with:
      otel_endpoint: "http://tempo:4318"  # Your OTLP HTTP endpoint
      # debug: "true"  # Enable to collect trace data in Component JSON
```

## Requirements

- An OTLP-compatible trace backend (Tempo, Jaeger, etc.)
- Network access from CI runners to the OTLP endpoint
- `jq` and `curl` available in the CI environment (provided by the default image)
