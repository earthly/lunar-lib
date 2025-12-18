# CI OpenTelemetry Collector

This collector emits OpenTelemetry traces for CI pipeline runs, providing detailed observability into CI job execution at the process level.

## Overview

The `ci-otel` collector instruments CI pipelines by creating distributed traces that capture:
- **Root span**: The entire CI job execution (identified by component, PR, and git SHA)
- **Command spans**: Individual process executions within the CI job (e.g., `git`, `docker`, `go`, etc.)

Traces are sent directly to a Tempo instance via OTLP HTTP, where they can be visualized in Grafana.

## How It Works

The collector hooks into Lunar's CI event system:

1. **`ci-before-job`**: Creates a root span and stores trace context in `/tmp/lunar-otel-trace-id`, `/tmp/lunar-otel-root-span-id`, and `/tmp/lunar-otel-job-start-time`
2. **`ci-before-command`**: Records the start time for each command in `/tmp/lunar-otel-cmd-{hash}`
3. **`ci-after-command`**: Reads the start time, calculates duration, and sends the command span to Tempo
4. **`ci-after-job`**: Reads the job start time, calculates total duration, and sends the root span to Tempo

## Current Implementation Limitation

**⚠️ Temporary File-Based Approach**
TODO actually this is safe.

This collector currently uses files on the host machine (`/tmp/lunar-otel-*`) to store trace context between start and end events. This works because:

- Start events write trace IDs, span IDs, and timestamps to files
- End events read from these files to construct complete spans with start/end times
- OpenTelemetry requires complete spans (with both start and end times) to be sent atomically

**Why this is temporary:**

This approach assumes all collector hooks run in the same execution environment with shared filesystem access. However, if collectors run in isolated containers or separate processes, they may not have access to the same `/tmp` directory, causing trace context to be lost.

**Future improvements:**

We plan to improve this to work more generically using an external datastore such as:
- **PostgreSQL**: Store trace context in a shared database
- **Shared filesystem**: Use a mounted volume accessible to all collector instances
- **Distributed cache**: Use Redis or similar for trace context storage

This will enable the collector to work reliably across containerized and distributed CI environments.

## Configuration

The collector accepts one input:

- `otel_endpoint`: The OTLP HTTP endpoint for sending traces (default: `http://tempo:4318`)

## Trace Structure

- **Service name**: `lunar-ci`
- **Root span name**: `{component_id} [#{pr}] {short_sha}` (e.g., `pantalasa #123 abc1234`)
- **Command span names**: First 50 characters of the command
- **Attributes**: Includes component metadata, command hashes, and CI-specific information

## Example

A typical trace might look like:
```
lunar-ci: pantalasa #123 abc1234 (root span, 1m 6s)
  ├─ ["/usr/bin/git","version"] (89.49ms)
  ├─ ["/usr/bin/git","checkout","--detach"] (94.06ms)
  ├─ ["/usr/bin/git","submodule","status"] (4.23s)
  │   ├─ ["/bin/sh","/usr/lib/git-core/git-submodule","status"] (4.01s)
  │   └─ ["basename","/usr/lib/git-core/git-submodule"] (186.77ms)
  └─ ["go","test","-v","./..."] (31.78ms)
```

