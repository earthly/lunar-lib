VERSION 0.8

FROM alpine:3.21

lint:
    FROM python:3.12-alpine
    WORKDIR /workspace
    COPY --dir collectors policies scripts .
    RUN python scripts/enforce_collector_readme_structure.py
    RUN python scripts/enforce_policy_readme_structure.py

ai-context:
    COPY --dir ai-context .
    SAVE ARTIFACT ai-context

all:
    BUILD --pass-args +base-image
    BUILD --pass-args ./collectors/dockerfile+image
    BUILD --pass-args ./collectors/ast-grep+image

base-image:
    ARG SCRIPTS_VERSION=main-alpine
    FROM earthly/lunar-scripts:$SCRIPTS_VERSION
    ARG VERSION=main
    SAVE IMAGE --push earthly/lunar-lib:base-$VERSION
