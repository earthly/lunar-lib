#!/bin/bash
set -e

source "${LUNAR_PLUGIN_ROOT}/otel-helpers.sh"

trace_id=$(cat /tmp/lunar-otel-trace-id-${LUNAR_CI_JOB_ID:-unknown} 2>/dev/null || echo "")
root_span_id=$(cat /tmp/lunar-otel-root-span-id-${LUNAR_CI_JOB_ID:-unknown} 2>/dev/null || echo "")

if [ -z "$trace_id" ] || [ -z "$root_span_id" ]; then
  echo "OTEL: No trace context found, skipping command span (trace_id='$trace_id', root_span_id='$root_span_id')" >&2
  # Use a temporary key for skipped events without trace_id
  skip_key="skipped_$(date +%s%N | head -c 13)_pid_${LUNAR_CI_COMMAND_PID:-unknown}"
  debug_collect ".ci.debug.cmd_start.$skip_key.status" "skipped_no_context"
  exit 0
fi

# Debug: Log trace context for troubleshooting
echo "OTEL: cmd-start: trace_id=$trace_id, root_span_id=$root_span_id, step_index=${LUNAR_CI_STEP_INDEX:-}, cmd_pid=${LUNAR_CI_COMMAND_PID:-}" >&2

# Use command PID for span ID (convert to hex)
if [ -z "${LUNAR_CI_COMMAND_PID:-}" ]; then
  echo "OTEL: No command PID found, skipping command span"
  skip_key="skipped_$(date +%s%N | head -c 13)_no_pid"
  debug_collect ".ci.debug.cmd_start.$skip_key.status" "skipped_no_pid"
  exit 0
fi

# Only trace commands that belong to a step - filter out internal CI runner processes
# Commands without step_index are internal CI runner processes (like git, sed, basename, etc.)
# that don't map to user-defined CI workflow steps and should not be traced
if [ -z "${LUNAR_CI_STEP_INDEX:-}" ]; then
  echo "OTEL: Command does not belong to a step (no step_index), skipping internal CI runner process: ${LUNAR_CI_COMMAND:-}" >&2
  
  # Collect internal processes for debugging purposes
  # Include job_id, step_id, PID, PPID, and command in hash to make each command instance unique
  cmd_hash=$(echo -n "${LUNAR_CI_JOB_ID:-}-${LUNAR_CI_STEP_INDEX:-}-${LUNAR_CI_COMMAND_PID}-${LUNAR_CI_COMMAND_PPID:-}-${LUNAR_CI_COMMAND:-}" | sha256sum | awk '{print $1}')
  
  debug_collect ".ci.traces.$trace_id.internal_processes.$cmd_hash.command" "${LUNAR_CI_COMMAND:-}" \
    ".ci.traces.$trace_id.internal_processes.$cmd_hash.cmd_hash" "$cmd_hash" \
    ".ci.traces.$trace_id.internal_processes.$cmd_hash.cmd_pid" "${LUNAR_CI_COMMAND_PID}" \
    ".ci.traces.$trace_id.internal_processes.$cmd_hash.cmd_ppid" "${LUNAR_CI_COMMAND_PPID:-}" \
    ".ci.traces.$trace_id.internal_processes.$cmd_hash.status" "skipped_no_step_index"
  
  exit 0
fi

span_id=$(generate_command_span_id)
parent_span_id=$(get_command_parent_span_id)
start_time=$(nanoseconds)

# Ensure parent_span_id is never empty (commands should never be root spans)
# Commands must be children of steps or other commands, never the root job span
# If we can't determine a valid parent (step or command), skip sending this command span
if [ -z "$parent_span_id" ]; then
  echo "OTEL: Warning - cannot determine step or command parent for command, skipping" >&2
  debug_collect ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.${LUNAR_CI_COMMAND_PID}.cmd_start.status" "skipped_no_parent" \
    ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.${LUNAR_CI_COMMAND_PID}.cmd_start.cmd_pid" "${LUNAR_CI_COMMAND_PID}" \
    ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.${LUNAR_CI_COMMAND_PID}.cmd_start.step_index" "${LUNAR_CI_STEP_INDEX}" \
    ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.${LUNAR_CI_COMMAND_PID}.cmd_start.cmd_ppid" "${LUNAR_CI_COMMAND_PPID:-}" \
    ".ci.traces.$trace_id.debug.steps.${LUNAR_CI_STEP_INDEX}.commands.${LUNAR_CI_COMMAND_PID}.cmd_start.cmd" "${LUNAR_CI_COMMAND:-}"

  exit 0
fi

# Generate command hash for structured collection and file naming
# Include job_id, step_id, PID, PPID, and command in hash to make each command instance unique
cmd_hash=$(echo -n "${LUNAR_CI_JOB_ID:-}-${LUNAR_CI_STEP_INDEX}-${LUNAR_CI_COMMAND_PID}-${LUNAR_CI_COMMAND_PPID:-}-${LUNAR_CI_COMMAND:-}" | sha256sum | awk '{print $1}')

# Store span info keyed by cmd_hash so we can look it up later
# Format: start_time,span_id,parent_span_id,command
cmd_file="/tmp/lunar-otel-cmd-${cmd_hash}"
echo "cmd_file: $cmd_file"
echo "$start_time" > "$cmd_file"
echo "$span_id" >> "$cmd_file"
echo "$parent_span_id" >> "$cmd_file"
echo "$LUNAR_CI_COMMAND" >> "$cmd_file"
echo "cmd_file contents: $(cat $cmd_file)"
echo "/tmp dir content:  $(ls -la /tmp)"

# Also store PID -> span_id mapping for parent lookups
# Use job_id-step_id-pid to ensure uniqueness across different jobs/steps (PIDs can be reused)
pid_map_file="/tmp/lunar-otel-pid-${LUNAR_CI_JOB_ID:-unknown}-${LUNAR_CI_STEP_INDEX:-unknown}-${LUNAR_CI_COMMAND_PID}"
echo "$span_id" > "$pid_map_file"

# Structured collection for debugging: Create command object (we know step_index exists because we filtered above)
debug_collect ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.command" "${LUNAR_CI_COMMAND:-}" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.cmd_hash" "$cmd_hash" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.cmd_pid" "${LUNAR_CI_COMMAND_PID}" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.cmd_ppid" "${LUNAR_CI_COMMAND_PPID:-}" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.span_id" "$span_id" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.parent_span_id" "$parent_span_id" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.start_time" "$start_time" \
  ".ci.traces.$trace_id.steps.${LUNAR_CI_STEP_INDEX}.commands.$cmd_hash.status" "started"
