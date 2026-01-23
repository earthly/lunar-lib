FROM earthly/lunar-scripts:1.0.0

# Install Go
RUN apk add --no-cache go

# Install golangci-lint
ARG GOLANGCI_LINT_VERSION=v1.57.1
ARG TARGETARCH=amd64
RUN curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | \
    sh -s -- -b /usr/local/bin ${GOLANGCI_LINT_VERSION}

# Verify installations
RUN go version && golangci-lint --version
