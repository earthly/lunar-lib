#!/bin/bash
set -e
DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends npm
npm install -g @roadiehq/backstage-entity-validator