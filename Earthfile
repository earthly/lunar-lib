VERSION 0.8

FROM alpine:3.21

# Export guardrails YAML and README data for website landing pages
guardrails-data:
    WORKDIR /build
    
    # Copy all source directories
    COPY --dir collectors policies catalogers .
    
    # Process into guardrails structure using shell loops
    RUN mkdir -p guardrails/collectors guardrails/policies guardrails/catalogers && \
        for dir in collectors/*/; do \
            name=$(basename "$dir"); \
            mkdir -p "guardrails/collectors/$name"; \
            cp "$dir/lunar-collector.yml" "guardrails/collectors/$name/" 2>/dev/null || true; \
            cp "$dir/README.md" "guardrails/collectors/$name/" 2>/dev/null || true; \
        done && \
        for dir in policies/*/; do \
            name=$(basename "$dir"); \
            mkdir -p "guardrails/policies/$name"; \
            cp "$dir/lunar-policy.yml" "guardrails/policies/$name/" 2>/dev/null || true; \
            cp "$dir/README.md" "guardrails/policies/$name/" 2>/dev/null || true; \
        done && \
        for dir in catalogers/*/; do \
            name=$(basename "$dir"); \
            mkdir -p "guardrails/catalogers/$name"; \
            cp "$dir/lunar-cataloger.yml" "guardrails/catalogers/$name/" 2>/dev/null || true; \
            cp "$dir/README.md" "guardrails/catalogers/$name/" 2>/dev/null || true; \
        done
    
    SAVE ARTIFACT guardrails

# Export guardrails icon assets for website
guardrails-assets:
    WORKDIR /build
    
    # Copy all source directories
    COPY --dir collectors policies catalogers .
    
    # Copy assets preserving plugin directory structure: icons/{type}/{plugin-name}/
    RUN mkdir -p icons && \
        for dir in collectors/*/assets; do \
            plugin=$(basename $(dirname "$dir")); \
            mkdir -p "icons/collectors/$plugin"; \
            cp -r "$dir"/* "icons/collectors/$plugin/" 2>/dev/null || true; \
        done && \
        for dir in policies/*/assets; do \
            plugin=$(basename $(dirname "$dir")); \
            mkdir -p "icons/policies/$plugin"; \
            cp -r "$dir"/* "icons/policies/$plugin/" 2>/dev/null || true; \
        done && \
        for dir in catalogers/*/assets; do \
            plugin=$(basename $(dirname "$dir")); \
            mkdir -p "icons/catalogers/$plugin"; \
            cp -r "$dir"/* "icons/catalogers/$plugin/" 2>/dev/null || true; \
        done
    
    SAVE ARTIFACT icons

test:
    BUILD ./collectors/codeowners+test

lint:
    FROM python:3.12-alpine
    WORKDIR /workspace
    COPY --dir catalogers collectors policies scripts .
    # Unified README structure validation for all plugin types
    RUN python scripts/validate_readme_structure.py
    # Landing page metadata validation for all plugin types
    RUN python scripts/validate_landing_page_metadata.py
    # SVG icon grayscale validation (rgb colors get flattened on the website)
    RUN python scripts/validate_svg_grayscale.py

ai-context:
    COPY --dir ai-context .
    SAVE ARTIFACT ai-context

all:
    BUILD --pass-args +base-image
    BUILD --pass-args ./collectors/ast-grep+image
    BUILD --pass-args ./collectors/claude+image
    BUILD --pass-args ./collectors/dockerfile+image
    BUILD --pass-args ./collectors/golang+image
    BUILD --pass-args ./collectors/nodejs+image
    BUILD --pass-args ./collectors/syft+image
    BUILD --pass-args ./catalogers/github-org+image

base-image:
    ARG SCRIPTS_VERSION=main-alpine
    FROM earthly/lunar-scripts:$SCRIPTS_VERSION
    # Add postgresql-client for collectors that need to query the Hub database
    RUN apk add --no-cache postgresql-client
    ARG VERSION=main
    SAVE IMAGE --push earthly/lunar-lib:base-$VERSION
