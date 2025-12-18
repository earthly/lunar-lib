#!/bin/bash

set -e

# Collect the UUID written by the autotest script (strip trailing newline)
printf '%s' "$(cat autotest.value)" | lunar collect ".autotest.value" -
