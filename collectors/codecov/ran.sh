#!/bin/bash
set -e
# Write minimal object - presence signals codecov ran
lunar collect -j ".testing.coverage.source" '{"tool": "codecov", "integration": "ci"}'
