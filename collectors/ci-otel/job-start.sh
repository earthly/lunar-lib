#!/bin/bash
set -e

source "${LUNAR_PLUGIN_ROOT}/otel-helpers.sh"

# Generate trace ID from component + job ID
trace_id=$(generate_trace_id)
root_span_id=$(generate_job_span_id)
start_time=$(nanoseconds)

# Store trace context for child spans
echo "$trace_id" > /tmp/lunar-otel-trace-id
echo "$root_span_id" > /tmp/lunar-otel-root-span-id
echo "$start_time" > /tmp/lunar-otel-job-start-time-${LUNAR_CI_JOB_ID:-unknown}

# Structured collection for debugging: Create root trace object
debug_collect ".ci.traces.$trace_id.trace_id" "$trace_id" \
  ".ci.traces.$trace_id.root_span_id" "$root_span_id" \
  ".ci.traces.$trace_id.job_id" "${LUNAR_CI_JOB_ID:-}" \
  ".ci.traces.$trace_id.job_name" "${LUNAR_CI_JOB_NAME:-unknown}" \
  ".ci.traces.$trace_id.component_id" "${LUNAR_COMPONENT_ID:-}" \
  ".ci.traces.$trace_id.git_sha" "${LUNAR_COMPONENT_GIT_SHA:-}" \
  ".ci.traces.$trace_id.pr" "${LUNAR_COMPONENT_PR:-}" \
  ".ci.traces.$trace_id.start_time" "$start_time" \
  ".ci.traces.$trace_id.status" "started"

echo "OTEL: Started trace $trace_id for job"

