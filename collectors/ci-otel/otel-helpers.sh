#!/bin/bash
# OTEL helper functions for CI tracing

# Endpoint from collector input (LUNAR_VAR_otel_endpoint) or fallback
# Send directly to Tempo (port 4318 is OTLP HTTP)
OTEL_ENDPOINT="${LUNAR_VAR_otel_endpoint:-${LUNAR_VAR_OTEL_ENDPOINT:-http://tempo:4318}}"

# Log a debug message to stderr (only when debug mode is enabled)
log_debug() {
  if [ "${LUNAR_VAR_debug:-${LUNAR_VAR_DEBUG:-false}}" = "true" ]; then
    echo "OTEL: $*" >&2
  fi
}

# Helper function to conditionally run debug collection
# Usage: debug_collect "key1" "value1" "key2" "value2" ...
debug_collect() {
  local debug_val="${LUNAR_VAR_debug:-${LUNAR_VAR_DEBUG:-false}}"
  if [ "$debug_val" = "true" ]; then
    lunar collect "$@" 2>/dev/null || true
  fi
}

# Convert a number to a 16-char hex span ID (pads with zeros)
pid_to_span_id() {
  local pid="$1"
  # Convert to hex, pad to 16 chars with zeros
  printf "%016x" "$pid" 2>/dev/null || echo -n "$pid" | xxd -p | head -c 16 | xargs printf "%016s" | tr ' ' '0'
}

# Convert a string to a 32-char hex trace ID
string_to_trace_id() {
  local input="$1"
  echo -n "$input" | sha256sum | cut -c1-32
}

# Generate a 32-char hex trace ID from component + CI job ID + run attempt
generate_trace_id() {
  local seed=""
  
  # Use component ID as base
  seed="${LUNAR_COMPONENT_ID:-unknown}"
  
  # Use CI job ID if available, otherwise fallback to timestamp
  if [ -n "${LUNAR_CI_JOB_ID:-}" ]; then
    seed="${seed}-${LUNAR_CI_JOB_ID}"
    # Include run attempt to distinguish retries (only if > 0)
    if [ -n "${LUNAR_CI_PIPELINE_RUN_ATTEMPT:-}" ] && [ "${LUNAR_CI_PIPELINE_RUN_ATTEMPT}" -gt 0 ] 2>/dev/null; then
      seed="${seed}-${LUNAR_CI_PIPELINE_RUN_ATTEMPT}"
    fi
  else
    seed="${seed}-$(date +%s%N)"
  fi
  
  # Hash to get consistent 32-char hex
  string_to_trace_id "$seed"
}

# Generate a 16-char hex span ID from CI job ID + run attempt
generate_job_span_id() {
  if [ -n "${LUNAR_CI_JOB_ID:-}" ]; then
    # Include run attempt to distinguish retries (only if > 0)
    local job_id_with_attempt="${LUNAR_CI_JOB_ID}"
    if [ -n "${LUNAR_CI_PIPELINE_RUN_ATTEMPT:-}" ] && [ "${LUNAR_CI_PIPELINE_RUN_ATTEMPT}" -gt 0 ] 2>/dev/null; then
      job_id_with_attempt="${job_id_with_attempt}-${LUNAR_CI_PIPELINE_RUN_ATTEMPT}"
    fi
    # Use job ID + attempt (hash to get consistent hex)
    string_to_trace_id "$job_id_with_attempt" | cut -c1-16
  else
    # Fallback: generate random span ID
    head -c 8 /dev/urandom | xxd -p
  fi
}

# Generate a 16-char hex span ID from CI step index
# Uses LUNAR_CI_JOB_ID + "-step-" + LUNAR_CI_STEP_INDEX for global uniqueness
# The "step-" prefix ensures it doesn't collide with job span ID (which uses job_id + "-" + run_attempt)
generate_step_span_id() {
  local step_id="${LUNAR_CI_JOB_ID}-step-${LUNAR_CI_STEP_INDEX}"
  string_to_trace_id "$step_id" | cut -c1-16
}

# Generate a 16-char hex span ID from command PID
generate_command_span_id() {
  if [ -n "${LUNAR_CI_COMMAND_PID:-}" ]; then
    pid_to_span_id "$LUNAR_CI_COMMAND_PID"
  else
    # Fallback: generate random span ID
    head -c 8 /dev/urandom | xxd -p
  fi
}

# Get parent span ID for a command
# Returns step span ID if PPID is not set, otherwise returns span ID for PPID
# Commands should NEVER use root_span_id as parent - they must be children of steps or other commands
# This ensures commands can never become root spans even if the job span isn't sent
get_command_parent_span_id() {
  if [ -n "${LUNAR_CI_COMMAND_PPID:-}" ]; then
    # Parent is another command - look up its span ID from stored mapping
    # Use job_id-step_id-ppid to ensure uniqueness (PIDs can be reused across different jobs/steps)
    # If not found, convert PPID directly to span ID (parent command may not have been traced)
    local parent_span_id
    pid_map_file="/tmp/lunar-otel-pid-${LUNAR_CI_JOB_ID:-unknown}-${LUNAR_CI_STEP_INDEX:-unknown}-${LUNAR_CI_COMMAND_PPID}"
    parent_span_id=$(cat "$pid_map_file" 2>/dev/null)
    if [ -n "$parent_span_id" ]; then
      echo "$parent_span_id"
    else
      # Fallback: convert PPID to span ID directly
      pid_to_span_id "$LUNAR_CI_COMMAND_PPID"
    fi
  else
    # Parent is the step (step hooks guarantee LUNAR_CI_STEP_INDEX is set)
    # If step span ID generation fails, return empty (command will be skipped)
    # We do NOT fall back to root_span_id to prevent commands from becoming root spans
    generate_step_span_id 2>/dev/null || echo ""
  fi
}

# Generate a 16-char hex span ID (fallback for when no specific ID is available)
generate_span_id() {
  # Use /dev/urandom for uniqueness
  head -c 8 /dev/urandom | xxd -p
}

# Get current time in nanoseconds since epoch
nanoseconds() {
  if date +%s%N | grep -q 'N'; then
    # macOS doesn't support %N, use seconds * 1e9
    echo "$(($(date +%s) * 1000000000))"
  else
    date +%s%N
  fi
}

# Build the base job/root span name: Use job name, fallback to component_id git_sha #PR
build_job_span_name() {
  # Prefer job name if available
  if [ -n "${LUNAR_CI_JOB_NAME:-}" ]; then
    echo "$LUNAR_CI_JOB_NAME"
    return
  fi

  # Fallback to component_id git_sha #PR format
  # Use short SHA (first 7 chars)
  local short_sha
  short_sha=$(echo "${LUNAR_COMPONENT_GIT_SHA:-}" | cut -c1-7)

  local name="$LUNAR_COMPONENT_ID"
  if [ -n "$short_sha" ]; then
    name="$name $short_sha"
  fi
  if [ -n "$LUNAR_COMPONENT_PR" ]; then
    name="$name #$LUNAR_COMPONENT_PR"
  fi

  echo "$name"
}

# Build attributes JSON for the job/root span
build_job_attributes() {
  local attrs="[]"
  
  # Component info from Lunar
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_ID:-}" '. + [{"key": "lunar.component_id", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_PR:-}" '. + [{"key": "lunar.pr", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_GIT_SHA:-}" '. + [{"key": "lunar.git_sha", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_DOMAIN:-}" '. + [{"key": "lunar.domain", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_OWNER:-}" '. + [{"key": "lunar.owner", "value": {"stringValue": $v}}]')

  # CI vendor (hardcoded for now)
  # TODO: Replace with LUNAR_CI_VENDOR when available
  attrs=$(echo "$attrs" | jq --arg v "github-actions" '. + [{"key": "ci.vendor", "value": {"stringValue": $v}}]')
  
  # Span type identifier
  attrs=$(echo "$attrs" | jq --arg v "job" '. + [{"key": "ci.span_type", "value": {"stringValue": $v}}]')
  
  # CI job metadata
  if [ -n "${LUNAR_CI_JOB_ID:-}" ]; then
    attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_JOB_ID}" '. + [{"key": "ci.job_id", "value": {"stringValue": $v}}]')
  fi
  if [ -n "${LUNAR_CI_JOB_NAME:-}" ]; then
    attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_JOB_NAME}" '. + [{"key": "ci.job_name", "value": {"stringValue": $v}}]')
  fi
  if [ -n "${LUNAR_CI_PIPELINE_RUN_ID:-}" ]; then
    attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_PIPELINE_RUN_ID}" '. + [{"key": "ci.pipeline_run_id", "value": {"stringValue": $v}}]')
  fi
  if [ -n "${LUNAR_CI_PIPELINE_RUN_ATTEMPT:-}" ]; then
    attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_PIPELINE_RUN_ATTEMPT}" '. + [{"key": "ci.pipeline_run_attempt", "value": {"stringValue": $v}}]')
  fi
  if [ -n "${LUNAR_CI_PIPELINE_NAME:-}" ]; then
    attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_PIPELINE_NAME}" '. + [{"key": "ci.pipeline_name", "value": {"stringValue": $v}}]')
  fi
  if [ -n "${LUNAR_CI_PIPELINE_DEFINITION_REF:-}" ]; then
    attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_PIPELINE_DEFINITION_REF}" '. + [{"key": "ci.pipeline_definition_ref", "value": {"stringValue": $v}}]')
  fi
  
  echo "$attrs"
}

# Build attributes JSON for a step span
build_step_attributes() {
  local attrs="[]"
  
  # Component info from Lunar (match job span attributes)
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_ID:-}" '. + [{"key": "lunar.component_id", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_PR:-}" '. + [{"key": "lunar.pr", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_GIT_SHA:-}" '. + [{"key": "lunar.git_sha", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_DOMAIN:-}" '. + [{"key": "lunar.domain", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_OWNER:-}" '. + [{"key": "lunar.owner", "value": {"stringValue": $v}}]')
  
  # CI vendor (same as job spans)
  attrs=$(echo "$attrs" | jq --arg v "github-actions" '. + [{"key": "ci.vendor", "value": {"stringValue": $v}}]')
  
  # Span type identifier
  attrs=$(echo "$attrs" | jq --arg v "step" '. + [{"key": "ci.span_type", "value": {"stringValue": $v}}]')
  
  # CI job metadata
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_JOB_ID}" '. + [{"key": "ci.job_id", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_JOB_NAME}" '. + [{"key": "ci.job_name", "value": {"stringValue": $v}}]')
  
  # Step metadata
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_STEP_INDEX}" '. + [{"key": "ci.step_index", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_STEP_NAME}" '. + [{"key": "ci.step_name", "value": {"stringValue": $v}}]')
  
  echo "$attrs"
}

# Build attributes JSON for a command span
build_command_attributes() {
  local cmd="$1"
  local cmd_hash="$2"
  local attrs="[]"
  
  attrs=$(echo "$attrs" | jq --arg v "$cmd" '. + [{"key": "ci.command", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "$cmd_hash" '. + [{"key": "ci.command_hash", "value": {"stringValue": $v}}]')
  
  # Component info from Lunar (match job span attributes)
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_ID:-}" '. + [{"key": "lunar.component_id", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_PR:-}" '. + [{"key": "lunar.pr", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_GIT_SHA:-}" '. + [{"key": "lunar.git_sha", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_DOMAIN:-}" '. + [{"key": "lunar.domain", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_COMPONENT_OWNER:-}" '. + [{"key": "lunar.owner", "value": {"stringValue": $v}}]')
  
  # CI vendor (same as job/step spans)
  attrs=$(echo "$attrs" | jq --arg v "github-actions" '. + [{"key": "ci.vendor", "value": {"stringValue": $v}}]')
  
  # Span type identifier
  attrs=$(echo "$attrs" | jq --arg v "command" '. + [{"key": "ci.span_type", "value": {"stringValue": $v}}]')
  
  # Add PID information for debugging
  if [ -n "${LUNAR_CI_COMMAND_PID:-}" ]; then
    attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_COMMAND_PID}" '. + [{"key": "ci.command_pid", "value": {"stringValue": $v}}]')
  fi
  if [ -n "${LUNAR_CI_COMMAND_PPID:-}" ]; then
    attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_COMMAND_PPID}" '. + [{"key": "ci.command_ppid", "value": {"stringValue": $v}}]')
  fi
  
  # Extract the command binary name (basename of first array element)
  # cmd is a JSON array string like ["/usr/bin/git","version"]
  local cmd_bin
  if cmd_bin=$(echo "$cmd" | jq -r '.[0] // ""' 2>/dev/null); then
    # Extract basename (everything after the last /)
    cmd_bin="${cmd_bin##*/}"
    if [ -n "$cmd_bin" ]; then
      attrs=$(echo "$attrs" | jq --arg v "$cmd_bin" '. + [{"key": "ci.command_bin", "value": {"stringValue": $v}}]')
    fi
  fi
  
  # Always add job metadata (even if empty, for consistency)
  # Commands should always have job context since they're part of a CI job
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_JOB_ID:-}" '. + [{"key": "ci.job_id", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_JOB_NAME:-}" '. + [{"key": "ci.job_name", "value": {"stringValue": $v}}]')
  
  # Always add step metadata (even if empty, for consistency)
  # Note: Commands without step_index are filtered out in cmd-start.sh, so these should always be set
  # But we include them always for consistency and to make filtering easier
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_STEP_INDEX:-}" '. + [{"key": "ci.step_index", "value": {"stringValue": $v}}]')
  attrs=$(echo "$attrs" | jq --arg v "${LUNAR_CI_STEP_NAME:-}" '. + [{"key": "ci.step_name", "value": {"stringValue": $v}}]')
  
  echo "$attrs"
}

# Send a span to the OTEL collector via HTTP/JSON
send_span() {
  local trace_id="$1"
  local span_id="$2"
  local parent_span_id="$3"
  local name="$4"
  local start_time="$5"
  local end_time="$6"
  local attributes="$7"
  
  # Validate inputs
  if [ -z "$trace_id" ] || [ -z "$span_id" ] || [ -z "$name" ]; then
    echo "OTEL: ERROR - Missing required parameters: trace_id='$trace_id' span_id='$span_id' name='$name'" >&2
    return 1
  fi
  
  # Validate trace_id and span_id are hex strings (OpenTelemetry requirement)
  if ! echo "$trace_id" | grep -qE '^[0-9a-f]{32}$'; then
    echo "OTEL: ERROR - Invalid trace_id format (must be 32-char hex): '$trace_id'" >&2
    return 1
  fi
  if ! echo "$span_id" | grep -qE '^[0-9a-f]{16}$'; then
    echo "OTEL: ERROR - Invalid span_id format (must be 16-char hex): '$span_id'" >&2
    return 1
  fi
  
  # Validate parent_span_id format if provided (must be 16-char hex)
  if [ -n "$parent_span_id" ] && ! echo "$parent_span_id" | grep -qE '^[0-9a-f]{16}$'; then
    echo "OTEL: ERROR - Invalid parent_span_id format (must be 16-char hex): '$parent_span_id'" >&2
    return 1
  fi
  
  # Validate times are numeric
  if ! echo "$start_time" | grep -qE '^[0-9]+$' || ! echo "$end_time" | grep -qE '^[0-9]+$'; then
    echo "OTEL: ERROR - Invalid time format: start_time='$start_time' end_time='$end_time'" >&2
    return 1
  fi
  
  # Validate attributes is valid JSON array
  if ! echo "$attributes" | jq -e '. | type == "array"' >/dev/null 2>&1; then
    echo "OTEL: ERROR - Invalid attributes format (must be JSON array): '$attributes'" >&2
    return 1
  fi
  
  # Build the span JSON
  local span_json
  if ! span_json=$(jq -n \
    --arg trace_id "$trace_id" \
    --arg span_id "$span_id" \
    --arg parent_span_id "$parent_span_id" \
    --arg name "$name" \
    --arg start_time "$start_time" \
    --arg end_time "$end_time" \
    --argjson attributes "$attributes" \
    '{
      traceId: $trace_id,
      spanId: $span_id,
      name: $name,
      startTimeUnixNano: $start_time,
      endTimeUnixNano: $end_time,
      attributes: $attributes,
      kind: 1,
      status: {
        code: 1
      }
    } + (if $parent_span_id != "" then {parentSpanId: $parent_span_id} else {} end)' 2>&1); then
    echo "OTEL: ERROR - Failed to build span JSON: $span_json" >&2
    return 1
  fi
  
  # Wrap in OTLP structure
  local otlp_payload

  if ! otlp_payload=$(jq -n \
    --argjson span "$span_json" \
    --arg service_name "$LUNAR_COMPONENT_ID" \
    '{
      resourceSpans: [{
        resource: {
          attributes: [
            {"key": "service.name", "value": {"stringValue": $service_name}}
          ]
        },
        scopeSpans: [{
          scope: {
            name: "lunar-ci-otel",
            version: "1.0.0"
          },
          spans: [$span]
        }]
      }]
    }' 2>&1); then
    echo "OTEL: ERROR - Failed to build OTLP payload: $otlp_payload" >&2
    return 1
  fi
  
  # Send to Tempo
  log_debug "Sending span '$name' (trace_id=$trace_id, span_id=$span_id, parent=$parent_span_id) to $OTEL_ENDPOINT"
  
  # Debug: Validate the span JSON structure before sending
  if ! echo "$span_json" | jq -e '.traceId and .spanId and .name and .startTimeUnixNano and .endTimeUnixNano' >/dev/null 2>&1; then
    echo "OTEL: ERROR - Span JSON missing required fields: $(echo "$span_json" | jq -c '.')" >&2
    return 1
  fi
  
  # Debug: Log the span structure (gated to avoid leaking sensitive data)
  if [ "${LUNAR_VAR_debug:-${LUNAR_VAR_DEBUG:-false}}" = "true" ]; then
    local span_preview
    span_preview=$(echo "$span_json" | jq -c '.' 2>/dev/null | head -c 500)
    log_debug "Span JSON preview: $span_preview..."
  fi
  
  local response
  local curl_exit_code=0
  response=$(curl -s -w "\n%{http_code}" -X POST \
    --connect-timeout "${OTEL_CONNECT_TIMEOUT:-5}" \
    --max-time "${OTEL_TIMEOUT:-10}" \
    "${OTEL_ENDPOINT}/v1/traces" \
    -H "Content-Type: application/json" \
    -d "$otlp_payload" 2>&1) || curl_exit_code=$?
  
  if [ $curl_exit_code -ne 0 ]; then
    echo "OTEL: ERROR - curl failed with exit code $curl_exit_code: $response" >&2
    return 1
  fi
  
  local http_code=$(echo "$response" | tail -n1)
  local body=$(echo "$response" | sed '$d')
  
  if [ "$http_code" = "200" ] || [ "$http_code" = "202" ]; then
    log_debug "Successfully sent span '$name' (HTTP $http_code, trace_id=$trace_id)"
    return 0
  else
    echo "OTEL: Failed to send span '$name' to $OTEL_ENDPOINT (HTTP $http_code, trace_id=$trace_id): $body" >&2
    return 1
  fi
}

