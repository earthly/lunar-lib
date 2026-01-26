VERSION 0.8

FROM alpine:3.21

ai-context:
    COPY --dir ai-context .
    SAVE ARTIFACT ai-context

all:
    BUILD --pass-args +base-image
    BUILD --pass-args ./collectors/dockerfile+image
    BUILD --pass-args ./collectors/golang+image

base-image:
    ARG SCRIPTS_VERSION=main-alpine
    FROM earthly/lunar-scripts:$SCRIPTS_VERSION
    ARG VERSION=main
    SAVE IMAGE --push earthly/lunar-lib:base-$VERSION
