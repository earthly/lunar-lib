#!/bin/bash
set -e

source "${LUNAR_PLUGIN_ROOT}/otel-helpers.sh"

trace_id=$(cat /tmp/lunar-otel-trace-id-${LUNAR_CI_JOB_ID:-unknown} 2>/dev/null || echo "")
root_span_id=$(cat /tmp/lunar-otel-root-span-id-${LUNAR_CI_JOB_ID:-unknown} 2>/dev/null || echo "")

if [ -z "$trace_id" ] || [ -z "$root_span_id" ]; then
  # Use a temporary key for skipped events without trace_id
  skip_key="skipped_$(date +%s%N | head -c 13)_pid_${LUNAR_CI_COMMAND_PID:-unknown}"
  debug_collect ".ci.debug.cmd_end.$skip_key.status" "skipped_no_context"
  exit 0
fi

# Use command PID to look up span info
if [ -z "${LUNAR_CI_COMMAND_PID:-}" ]; then
  log_debug "No command PID found, skipping command span"
  skip_key="skipped_$(date +%s%N | head -c 13)_no_pid"
  debug_collect ".ci.debug.cmd_end.$skip_key.status" "skipped_no_pid"
  exit 0
fi

# Only trace commands that belong to a step - filter out internal CI runner processes
# Commands without step_index are internal CI runner processes (like git, sed, basename, etc.)
# that don't map to user-defined CI workflow steps and should not be traced
if [ -z "${LUNAR_CI_STEP_INDEX:-}" ]; then
  log_debug "Command does not belong to a step (no step_index), skipping internal CI runner process"
  
  # Debug logging under internal_processes category
  debug_collect ".ci.traces.$trace_id.debug.internal_processes.${LUNAR_CI_COMMAND_PID}.cmd_end.status" "skipped_no_step_index" \
    ".ci.traces.$trace_id.debug.internal_processes.${LUNAR_CI_COMMAND_PID}.cmd_end.cmd_pid" "${LUNAR_CI_COMMAND_PID}" \
    ".ci.traces.$trace_id.debug.internal_processes.${LUNAR_CI_COMMAND_PID}.cmd_end.cmd" "${LUNAR_CI_COMMAND:-}"
  
  exit 0
fi

# Generate command hash to look up the start time file
# Include job_id, step_id, PID, PPID, and command in hash to make each command instance unique
cmd_hash=$(echo -n "${LUNAR_CI_JOB_ID:-}-${LUNAR_CI_STEP_INDEX}-${LUNAR_CI_COMMAND_PID}-${LUNAR_CI_COMMAND_PPID:-}-${LUNAR_CI_COMMAND:-}" | sha256sum | awk '{print $1}')

cmd_file="/tmp/lunar-otel-cmd-${cmd_hash}"

# Debug logging (gated to avoid leaking secrets in CI logs)
log_debug "cmd_file=$cmd_file"

# Make sure the file exists and has content
if ! head -n 1 "$cmd_file" >/dev/null 2>&1; then
  log_debug "No start time found for command hash ${cmd_hash}, skipping"
  debug_collect ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.cmd_end.status" "skipped_no_start" \
    ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.cmd_end.cmd_pid" "${LUNAR_CI_COMMAND_PID}" \
    ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.cmd_end.command" "${LUNAR_CI_COMMAND:-}"
  exit 0
fi

start_time=$(sed -n '1p' "$cmd_file")
span_id=$(sed -n '2p' "$cmd_file")
parent_span_id=$(sed -n '3p' "$cmd_file")
# Get the command from the stored file
stored_cmd=$(sed -n '4p' "$cmd_file")
cmd="$stored_cmd"
end_time=$(nanoseconds)

# Ensure parent_span_id is never empty (commands should never be root spans)
# Commands must be children of steps or other commands, never the root job span
# If parent_span_id is empty, skip sending this command span
if [ -z "$parent_span_id" ]; then
  log_debug "Warning - command parent span ID is empty, skipping command span"
  debug_collect ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.cmd_end.status" "skipped_empty_parent" \
    ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.cmd_end.cmd_pid" "${LUNAR_CI_COMMAND_PID}" \
    ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.cmd_end.span_id" "$span_id" \
    ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.cmd_end.cmd" "${LUNAR_CI_COMMAND:-}" \
    ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.cmd_end.step_index" "${LUNAR_CI_STEP_INDEX}"
  exit 0
fi

# Use the full command as span name
# cmd is a JSON array like ["/usr/bin/git","version"]
span_name="$cmd"

# Calculate duration
duration_ns=$((end_time - start_time))
duration_ms=$((duration_ns / 1000000))

# Structured collection for debugging: Update command object with completion info (we know step_index exists because we filtered above)
debug_collect ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.end_time" "$end_time" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.duration_ns" "$duration_ns" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.duration_ms" "$duration_ms" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.span_name" "$span_name" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.completed" "true"

# Build attributes before sending (to catch errors early)
cmd_attrs=$(build_command_attributes "$cmd" "$cmd_hash") || {
  echo "OTEL: ERROR - Failed to build command attributes" >&2
  exit 1
}

send_span \
  "$trace_id" \
  "$span_id" \
  "$parent_span_id" \
  "$span_name" \
  "$start_time" \
  "$end_time" \
  "$cmd_attrs" || {
  echo "OTEL: ERROR - Failed to send command span" >&2
  exit 1
}

# Cleanup
rm -f "$cmd_file"
pid_map_file="/tmp/lunar-otel-pid-${LUNAR_CI_JOB_ID:-unknown}-${LUNAR_CI_STEP_INDEX:-unknown}-${LUNAR_CI_COMMAND_PID}"
rm -f "$pid_map_file"

