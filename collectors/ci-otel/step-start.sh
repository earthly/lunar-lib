#!/bin/bash
set -e

source "${LUNAR_PLUGIN_ROOT}/otel-helpers.sh"

# For step 1, job-start.sh runs during ci-before-step, so there might be a race condition
# Retry reading trace context a few times if it's not available yet (especially for step 1)
trace_id=""
root_span_id=""
max_retries=5
retry_delay=0.1
retry_count=0

while [ -z "$trace_id" ] || [ -z "$root_span_id" ]; do
  trace_id=$(cat /tmp/lunar-otel-trace-id 2>/dev/null || echo "")
  root_span_id=$(cat /tmp/lunar-otel-root-span-id 2>/dev/null || echo "")
  
  if [ -n "$trace_id" ] && [ -n "$root_span_id" ]; then
    break
  fi
  
  if [ $retry_count -ge $max_retries ]; then
    echo "OTEL: No trace context found after ${max_retries} retries, skipping step span"
    # Use a temporary key for skipped events without trace_id
    skip_key="skipped_$(date +%s%N | head -c 13)_step_${LUNAR_CI_STEP_INDEX:-unknown}"
    debug_collect ".ci.debug.step_start.$skip_key.status" "skipped_no_context" \
      ".ci.debug.step_start.$skip_key.step_index" "${LUNAR_CI_STEP_INDEX:-}" \
      ".ci.debug.step_start.$skip_key.retries" "$retry_count"
    exit 0
  fi
  
  sleep $retry_delay
  retry_count=$((retry_count + 1))
done

# Generate step span ID from job ID + step index
step_span_id=$(generate_step_span_id)
start_time=$(nanoseconds)

# Store step span info for command parent lookups
echo "$step_span_id" > "/tmp/lunar-otel-step-${LUNAR_CI_STEP_INDEX}"
echo "$start_time" > "/tmp/lunar-otel-step-start-${LUNAR_CI_STEP_INDEX}"

# Structured collection for debugging: Create step object
debug_collect ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.step_index" "${LUNAR_CI_STEP_INDEX}" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.step_name" "${LUNAR_CI_STEP_NAME:-unknown}" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.step_span_id" "$step_span_id" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.start_time" "$start_time" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.status" "started"

# Don't send the span yet - OpenTelemetry spans are immutable
# We'll send it once when the step completes in step-end.sh
echo "OTEL: Started step span $step_span_id for step ${LUNAR_CI_STEP_INDEX} (span will be sent on completion)"

