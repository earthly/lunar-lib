#!/bin/bash
set -e

# CI collector - tracks all docker commands, with extra processing for specific subcommands.
# Runs native on CI runner — avoid jq and heavy dependencies.

# Convert LUNAR_CI_COMMAND from JSON array to string
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# --- Escape command for JSON ---
CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# --- Always: record every docker command to cicd.cmds ---
VERSION=$(docker version --format '{{.Client.Version}}' 2>/dev/null || echo "")
VERSION_ESCAPED=$(echo "$VERSION" | sed 's/\\/\\\\/g; s/"/\\"/g')

if [[ -n "$VERSION_ESCAPED" ]]; then
  echo "{\"cicd\":{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$VERSION_ESCAPED\"}],\"source\":{\"tool\":\"docker\",\"integration\":\"ci\"}}}" | \
    lunar collect -j ".containers.native.docker" -
else
  echo "{\"cicd\":{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\"}],\"source\":{\"tool\":\"docker\",\"integration\":\"ci\"}}}" | \
    lunar collect -j ".containers.native.docker" -
fi

# --- Detect subcommand (first non-flag arg after "docker") ---
SUBCOMMAND=""
for arg in $CMD_STR; do
  [[ "$arg" == "docker" ]] && continue
  [[ "$arg" == -* ]] && continue
  SUBCOMMAND="$arg"
  break
done

# =============================================================================
# Subcommand: build
# Parse flags and write normalized build metadata to .containers.builds[]
# =============================================================================
if [[ "$SUBCOMMAND" == "build" || "$SUBCOMMAND" == "buildx" ]]; then

  HAS_TAG=false
  IMAGE=""
  TAG=""
  PLATFORM=""
  DOCKERFILE=""

  # Accumulate labels as JSON object
  LABELS_JSON="{"
  LABEL_COUNT=0

  add_label() {
    local kv="$1"
    local key="${kv%%=*}"
    local val="${kv#*=}"
    key=$(echo "$key" | sed 's/\\/\\\\/g; s/"/\\"/g')
    val=$(echo "$val" | sed 's/\\/\\\\/g; s/"/\\"/g')
    if [[ $LABEL_COUNT -gt 0 ]]; then
      LABELS_JSON+=","
    fi
    LABELS_JSON+="\"$key\":\"$val\""
    LABEL_COUNT=$((LABEL_COUNT + 1))
  }

  # Parse image reference, handling registry:port correctly.
  parse_image_ref() {
    local ref="$1"
    local last_segment="${ref##*/}"
    if [[ "$last_segment" == *:* && "$ref" == */* ]]; then
      TAG="${last_segment##*:}"
      IMAGE="${ref%:*}"
    elif [[ "$ref" != */* && "$ref" == *:* ]]; then
      TAG="${ref##*:}"
      IMAGE="${ref%:*}"
    else
      IMAGE="$ref"
      TAG=""
    fi
  }

  prev=""
  for arg in $CMD_STR; do
    case "$prev" in
      -t|--tag)
        HAS_TAG=true
        parse_image_ref "$arg"
        prev=""
        continue
        ;;
      --platform)
        PLATFORM="$arg"
        prev=""
        continue
        ;;
      -f|--file)
        DOCKERFILE="$arg"
        prev=""
        continue
        ;;
      --label)
        if [[ "$arg" == *=* ]]; then
          add_label "$arg"
        fi
        prev=""
        continue
        ;;
    esac

    case "$arg" in
      -t=*|--tag=*)
        HAS_TAG=true
        parse_image_ref "${arg#*=}"
        continue
        ;;
      --platform=*)
        PLATFORM="${arg#*=}"
        continue
        ;;
      -f=*|--file=*)
        DOCKERFILE="${arg#*=}"
        continue
        ;;
      --label=*)
        label_val="${arg#--label=}"
        if [[ "$label_val" == *=* ]]; then
          add_label "$label_val"
        fi
        continue
        ;;
      --label)
        prev="--label"
        continue
        ;;
    esac

    if [[ "$arg" == "-t" || "$arg" == "--tag" || "$arg" == "--platform" || "$arg" == "-f" || "$arg" == "--file" ]]; then
      prev="$arg"
      continue
    fi

    prev=""
  done

  LABELS_JSON+="}"

  # Escape parsed values for JSON
  IMAGE_ESCAPED=$(echo "$IMAGE" | sed 's/\\/\\\\/g; s/"/\\"/g')
  TAG_ESCAPED=$(echo "$TAG" | sed 's/\\/\\\\/g; s/"/\\"/g')
  PLATFORM_ESCAPED=$(echo "$PLATFORM" | sed 's/\\/\\\\/g; s/"/\\"/g')
  DOCKERFILE_ESCAPED=$(echo "$DOCKERFILE" | sed 's/\\/\\\\/g; s/"/\\"/g')

  json_str_or_null() {
    if [[ -z "$1" ]]; then echo "null"; else echo "\"$1\""; fi
  }

  IMAGE_JSON=$(json_str_or_null "$IMAGE_ESCAPED")
  TAG_JSON=$(json_str_or_null "$TAG_ESCAPED")
  PLATFORM_JSON=$(json_str_or_null "$PLATFORM_ESCAPED")
  DOCKERFILE_JSON=$(json_str_or_null "$DOCKERFILE_ESCAPED")

  echo "[{\"cmd\":\"$CMD_ESCAPED\",\"has_tag\":$HAS_TAG,\"image\":$IMAGE_JSON,\"tag\":$TAG_JSON,\"labels\":$LABELS_JSON,\"expected_git_sha\":\"$LUNAR_COMPONENT_GIT_SHA\",\"platform\":$PLATFORM_JSON,\"dockerfile\":$DOCKERFILE_JSON}]" | \
    lunar collect -j ".containers.builds" -
fi

# =============================================================================
# Future subcommands can be added here:
# if [[ "$SUBCOMMAND" == "push" ]]; then ...
# if [[ "$SUBCOMMAND" == "pull" ]]; then ...
# =============================================================================
