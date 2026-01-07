VERSION 0.8

all:
    BUILD --pass-args +base-image
    BUILD --pass-args ./collectors/dockerfile+image

base-image:
    ARG SCRIPTS_VERSION=main
    FROM earthly/lunar-scripts:$SCRIPTS_VERSION
    RUN apt-get update && apt-get install -y curl jq parallel
    ARG VERSION=main
    SAVE IMAGE --push earthly/lunar-lib:base-$VERSION
