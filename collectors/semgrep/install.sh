#!/bin/bash
# Install dependencies for the semgrep collector

# postgresql-client is needed for the github-app-default-branch collector
# which queries the Lunar Hub database
apk add --no-cache postgresql-client
