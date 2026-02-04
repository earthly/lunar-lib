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
