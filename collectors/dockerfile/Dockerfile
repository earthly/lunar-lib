FROM earthly/lunar-scripts:v1.0

# Install dockerfile-json for parsing Dockerfiles to JSON AST
# Same tool and version used in lunar-cronos
ARG TARGETARCH=amd64
RUN ARCH=$(echo "${TARGETARCH}" | sed 's/amd64/x86_64/') && \
    curl -sSL "https://github.com/keilerkonzept/dockerfile-json/releases/download/v1.2.2/dockerfile-json_Linux_${ARCH}.tar.gz" | tar xz && \
    mv dockerfile-json /usr/local/bin/
