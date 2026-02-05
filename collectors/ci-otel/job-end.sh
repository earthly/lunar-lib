#!/bin/bash
set -e

source "${LUNAR_PLUGIN_ROOT}/otel-helpers.sh"

trace_id=$(cat /tmp/lunar-otel-trace-id-${LUNAR_CI_JOB_ID:-unknown} 2>/dev/null || echo "")
root_span_id=$(cat /tmp/lunar-otel-root-span-id-${LUNAR_CI_JOB_ID:-unknown} 2>/dev/null || echo "")
start_time=$(cat /tmp/lunar-otel-job-start-time-${LUNAR_CI_JOB_ID:-unknown} 2>/dev/null || echo "")
end_time=$(nanoseconds)

if [ -z "$trace_id" ] || [ -z "$root_span_id" ] || [ -z "$start_time" ]; then
  echo "OTEL: No trace context or start time found, skipping job end span"
  # Use a temporary key for skipped events without trace_id
  skip_key="skipped_$(date +%s%N | head -c 13)"
  debug_collect ".ci.debug.job_end.$skip_key.status" "skipped_no_context" \
    ".ci.debug.job_end.$skip_key.trace_id" "$trace_id" \
    ".ci.debug.job_end.$skip_key.root_span_id" "$root_span_id"
  exit 0
fi

# Debug: Log trace context
echo "OTEL: job-end: trace_id=$trace_id, root_span_id=$root_span_id, job_id=${LUNAR_CI_JOB_ID:-}" >&2

# Build and send the final root span
span_name="$(build_job_span_name)"

# Ensure span name is never empty (fallback to job ID if component info is missing)
if [ -z "$span_name" ]; then
  span_name="CI Job ${LUNAR_CI_JOB_ID:-unknown}"
fi

# Calculate duration
duration_ns=$((end_time - start_time))
duration_ms=$((duration_ns / 1000000))

# Structured collection for debugging: Update root trace object with completion info
debug_collect ".ci.traces.$trace_id.end_time" "$end_time" \
  ".ci.traces.$trace_id.duration_ns" "$duration_ns" \
  ".ci.traces.$trace_id.duration_ms" "$duration_ms" \
  ".ci.traces.$trace_id.span_name" "$span_name" \
  ".ci.traces.$trace_id.job_name" "${LUNAR_CI_JOB_NAME:-unknown}" \
  ".ci.traces.$trace_id.completed" "true"

# Build attributes before sending (to catch errors early)
job_attrs=$(build_job_attributes) || {
  echo "OTEL: ERROR - Failed to build job attributes" >&2
  debug_collect ".ci.traces.$trace_id.debug.job_end.errors.build_attributes_failed" "true"
  exit 1
}

send_span \
  "$trace_id" \
  "$root_span_id" \
  "" \
  "$span_name" \
  "$start_time" \
  "$end_time" \
  "$job_attrs" || {
  echo "OTEL: ERROR - Failed to send job span" >&2
  debug_collect ".ci.traces.$trace_id.debug.job_end.errors.send_span_failed" "true"
  exit 1
}

# Cleanup
rm -f /tmp/lunar-otel-trace-id-${LUNAR_CI_JOB_ID:-unknown} /tmp/lunar-otel-root-span-id-${LUNAR_CI_JOB_ID:-unknown} /tmp/lunar-otel-job-start-time-${LUNAR_CI_JOB_ID:-unknown}
