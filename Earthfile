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

# Export collector and policy source code
plugin-source:
    WORKDIR /build
    COPY --dir collectors policies .
    SAVE ARTIFACT collectors
    SAVE ARTIFACT policies

test:
    BUILD ./collectors/repo-boilerplate+test
    BUILD ./collectors/backstage+test
    BUILD --pass-args ./collectors/backstage+test-offline
    BUILD --pass-args ./collectors/ci-archive+test
    BUILD ./collectors/github+test
    BUILD ./collectors/gitlab+test
    BUILD ./collectors/jira+test
    BUILD --pass-args ./collectors/compliance-docs+test
    BUILD ./collectors/package-registries+test
    BUILD ./collectors/trivy+test
    BUILD ./collectors/grype+test
    BUILD ./collectors/docker+test
    BUILD ./collectors/codeql+test
    BUILD ./collectors/terraform+test
    BUILD --pass-args ./collectors/pagerduty+test
    BUILD ./collectors/k8s+test
    BUILD ./collectors/istio+test
    BUILD ./collectors/datadog+test
    BUILD ./collectors/argocd-deployment-tracking+test
    BUILD ./catalogers/backstage+test
    BUILD --pass-args ./catalogers/github-org+test
    BUILD --pass-args ./catalogers/moon+test
    BUILD ./probes/pr-title-ticket-ref+test
    BUILD ./probes/python+test
    BUILD ./policies/nodejs+test
    BUILD ./policies/ai+test
    BUILD ./policies/compliance-docs+test
    BUILD ./policies/git+test
    BUILD ./policies/vcs+test
    BUILD ./policies/backstage+test
    BUILD ./policies/k8s+test
    BUILD ./policies/istio+test
    BUILD ./policies/github-actions+test
    BUILD ./policies/sca+test
    BUILD ./policies/container-scan+test
    BUILD ./policies/repo-boilerplate+test
    BUILD ./policies/dependencies+test
    BUILD ./policies/container+test
    BUILD ./policies/terraform+test
    BUILD ./policies/sbom+test
    BUILD ./policies/oncall+test
    BUILD ./policies/ticket+test

lint:
    FROM python:3.12-alpine
    WORKDIR /workspace
    RUN pip install --quiet pyyaml
    COPY --dir ai-context catalogers collectors policies probes scripts starter-packs .
    COPY Earthfile .
    # Unified README structure validation for all plugin types
    RUN python scripts/validate_readme_structure.py
    # Landing page metadata validation for all plugin types
    RUN python scripts/validate_landing_page_metadata.py
    # SVG icon grayscale validation (rgb colors get flattened on the website)
    RUN python scripts/validate_svg_grayscale.py
    # Validate all plugin Earthfiles with image targets are wired into +all
    RUN python scripts/validate_earthfile_wiring.py
    # Validate earthly/lunar-lib image tags are canonical (-main / -vX.Y.Z), not dev/personal builds
    RUN python scripts/validate_image_tags.py
    # Unknown snippet/hook keys in plugin manifests (the hub drops them silently)
    RUN python scripts/validate_manifest_schema.py --self-test
    RUN python scripts/validate_manifest_schema.py
    # Every lunar-lib import in the docs lists what it runs with include:
    RUN python scripts/validate_readme_includes.py --self-test
    RUN python scripts/validate_readme_includes.py

ai-context:
    COPY --dir ai-context .
    SAVE ARTIFACT ai-context

all:
    BUILD --pass-args +base-image
    BUILD --pass-args ./collectors/argocd+image
    BUILD --pass-args ./collectors/ast-grep+image
    BUILD --pass-args ./collectors/claude+image
    BUILD --pass-args ./collectors/docker+image
    BUILD --pass-args ./collectors/k8s+image
    BUILD --pass-args ./collectors/istio+image
    BUILD --pass-args ./collectors/helm+image
    BUILD --pass-args ./collectors/golang+image
    BUILD --pass-args ./collectors/nodejs+image
    BUILD --pass-args ./collectors/syft+image
    BUILD --pass-args ./collectors/license-origins+image
    BUILD --pass-args ./collectors/terraform+image
    BUILD --pass-args ./collectors/trivy+image
    BUILD --pass-args ./collectors/grype+image
    BUILD --pass-args ./collectors/gitleaks+image
    BUILD --pass-args ./collectors/php+image
    BUILD --pass-args ./collectors/rust+image
    BUILD --pass-args ./collectors/cpp+image
    BUILD --pass-args ./collectors/github-actions+image
    BUILD --pass-args ./collectors/html+image
    BUILD --pass-args ./collectors/shell+image
    BUILD --pass-args ./collectors/ruby+image
    BUILD --pass-args ./collectors/elixir+image
    BUILD --pass-args ./collectors/checkov+image
    BUILD --pass-args ./catalogers/github-org+image
    BUILD --pass-args ./catalogers/moon+image
    BUILD --pass-args ./policies/dependencies+image

base-image:
    ARG SCRIPTS_VERSION=1.1.6-alpine
    FROM earthly/lunar-scripts:$SCRIPTS_VERSION
    # Pull in every OS-package security fix Alpine has published for the pinned
    # base. lunar-scripts only ever `apk add`s on top of a pinned alpine:<ver>,
    # so its tags ship whatever package set that base had when it was cut — e.g.
    # openssl 3.5.7-r0 with two fixable criticals while 3.5.8-r0 was already in
    # the 3.24 repo. Upgrading here is what keeps that out of every image built
    # on this base (21 of the 27 published images).
    # RUN --no-cache: re-run the upgrade on every build. Without it the layer is
    # served from the inline cache (--ci imports it from the previously pushed
    # base-<tag>), so -main images would stay frozen at whatever the first build
    # after a pin bump picked up. Release cuts and new branches never had a cache
    # to hit, so they were always fresh; this makes main behave the same.
    RUN --no-cache apk upgrade --no-cache
    # Replace the CLI and yq the pinned lunar-scripts tag froze in.
    COPY +lunar-cli/lunar /usr/bin/lunar
    COPY +yq-bin/yq /usr/local/bin/yq
    # Add postgresql-client for collectors that need to query the Hub database
    RUN apk add --no-cache postgresql-client
    # git: a dozen collectors shell out to it (diff, log, ls-files) and their
    # call sites swallow the failure, so without it they silently write nothing.
    # safe.directory: the snippet checkout is owned by a different uid than the
    # process running the script, which git otherwise refuses to read.
    RUN apk add --no-cache git && git config --system --add safe.directory '*'
    ARG VERSION=main
    SAVE IMAGE --push earthly/lunar-lib:base-$VERSION

# Latest released lunar CLI. A lunar-scripts tag freezes the CLI that was current
# when it was cut, so every image installs this one over it.
lunar-cli:
    FROM alpine:3.21
    RUN apk add --no-cache curl
    ARG TARGETARCH
    # Floats to the newest release on purpose. To roll back a bad one, set a
    # version here (e.g. 4.9.0) until a fixed release ships.
    ARG LUNAR_CLI_VERSION=latest
    # --no-cache: resolve "latest" on every build, not from the layer cache.
    RUN --no-cache if [ "$LUNAR_CLI_VERSION" = latest ]; then \
            url="https://github.com/earthly/lunar-dist/releases/latest/download/lunar-linux-${TARGETARCH}"; \
        else \
            url="https://github.com/earthly/lunar-dist/releases/download/v${LUNAR_CLI_VERSION}/lunar-linux-${TARGETARCH}"; \
        fi && \
        curl -fsSL -o /lunar "$url" && chmod 755 /lunar && /lunar version
    SAVE ARTIFACT /lunar

# kubeconform for the k8s and argocd images, built from source with a current
# x/text: the 0.8.0 release binary carries fixable Highs in it and in Go's stdlib.
kubeconform-bin:
    FROM golang:1.27-alpine
    RUN apk add --no-cache git
    # renovate: datasource=github-releases depName=yannh/kubeconform extractVersion=^v(?<version>.*)$
    ARG KUBECONFORM_VERSION=0.8.0
    RUN git clone --quiet --depth 1 --branch "v${KUBECONFORM_VERSION}" https://github.com/yannh/kubeconform /src
    WORKDIR /src
    # The repo vendors its dependencies, so re-vendor after the bump.
    RUN go get golang.org/x/text@latest && go mod vendor && \
        CGO_ENABLED=0 go build -trimpath -tags netgo \
            -ldflags "-s -w -X main.version=v${KUBECONFORM_VERSION}" -o /out/kubeconform ./cmd/kubeconform
    SAVE ARTIFACT /out/kubeconform

# Built from source so yq carries a current Go stdlib; upstream's release binaries
# lag the Go patch releases that fix stdlib CVEs.
yq-bin:
    FROM golang:1.27-alpine
    # renovate: datasource=github-releases depName=mikefarah/yq extractVersion=^v(?<version>.*)$
    ARG YQ_VERSION=4.54.1
    RUN CGO_ENABLED=0 go install "github.com/mikefarah/yq/v4@v${YQ_VERSION}"
    SAVE ARTIFACT /go/bin/yq
