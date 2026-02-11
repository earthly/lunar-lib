#!/bin/bash
set -e

source "${LUNAR_PLUGIN_ROOT}/otel-helpers.sh"

trace_id=$(cat /tmp/lunar-otel-trace-id-${LUNAR_CI_JOB_ID:-unknown} 2>/dev/null || echo "")
root_span_id=$(cat /tmp/lunar-otel-root-span-id-${LUNAR_CI_JOB_ID:-unknown} 2>/dev/null || echo "")

if [ -z "$trace_id" ] || [ -z "$root_span_id" ]; then
  log_debug "No trace context found, skipping step span"
  # Use a temporary key for skipped events without trace_id
  skip_key="skipped_$(date +%s%N | head -c 13)_step_${LUNAR_CI_STEP_INDEX:-unknown}"
  debug_collect ".ci.debug.step_end.$skip_key.status" "skipped_no_context" \
    ".ci.debug.step_end.$skip_key.step_index" "${LUNAR_CI_STEP_INDEX:-}"
  exit 0
fi

step_file="/tmp/lunar-otel-step-${LUNAR_CI_JOB_ID:-unknown}-${LUNAR_CI_STEP_INDEX}"
step_start_file="/tmp/lunar-otel-step-start-${LUNAR_CI_JOB_ID:-unknown}-${LUNAR_CI_STEP_INDEX}"

if [ ! -f "$step_file" ] || [ ! -f "$step_start_file" ]; then
  log_debug "No step start found for step ${LUNAR_CI_STEP_INDEX}, skipping"
  # Still try to mark the step as failed/not completed if we have trace context
  debug_collect ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.step_end.status" "skipped_no_start" \
    ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.step_end.step_index" "${LUNAR_CI_STEP_INDEX}"
  exit 0
fi

step_span_id=$(cat "$step_file")
start_time=$(cat "$step_start_file")
end_time=$(nanoseconds)

# Debug: Log trace context
log_debug "step-end: trace_id=$trace_id, root_span_id=$root_span_id, step_span_id=$step_span_id, step_index=${LUNAR_CI_STEP_INDEX:-}"

# Build step name with "Step" prefix, step index, then step name
step_name="Step ${LUNAR_CI_STEP_INDEX}: ${LUNAR_CI_STEP_NAME}"

# Calculate duration
duration_ns=$((end_time - start_time))
duration_ms=$((duration_ns / 1000000))

# Structured collection for debugging: Update step object with completion info
# Also update step_name in case it wasn't available at step-start but is available now
debug_collect ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.end_time" "$end_time" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.duration_ns" "$duration_ns" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.duration_ms" "$duration_ms" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.span_name" "$step_name" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.step_name" "${LUNAR_CI_STEP_NAME:-unknown}" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.completed" "true"

# Build attributes before sending (to catch errors early)
step_attrs=$(build_step_attributes) || {
  echo "OTEL: ERROR - Failed to build step attributes" >&2
  debug_collect ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.step_end.errors.build_attributes_failed" "true"
  exit 1
}

# Send final step span
send_span \
  "$trace_id" \
  "$step_span_id" \
  "$root_span_id" \
  "$step_name" \
  "$start_time" \
  "$end_time" \
  "$step_attrs" || {
  echo "OTEL: ERROR - Failed to send step span" >&2
  debug_collect ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.step_end.errors.send_span_failed" "true"
  exit 1
}

# Cleanup
rm -f "$step_file" "$step_start_file"

log_debug "Completed step span $step_span_id for step ${LUNAR_CI_STEP_INDEX}"

