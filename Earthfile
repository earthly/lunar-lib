VERSION 0.8

ai-context:
    COPY --dir ai-context .
    SAVE ARTIFACT ai-context

all:
    BUILD --pass-args +base-image
    BUILD --pass-args ./collectors/dockerfile+image

base-image:
    ARG SCRIPTS_VERSION=main-alpine
    FROM earthly/lunar-scripts:$SCRIPTS_VERSION
    ARG VERSION=main
    SAVE IMAGE --push earthly/lunar-lib:base-$VERSION
