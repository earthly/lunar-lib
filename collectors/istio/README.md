# Istio Collector

Parses Istio service-mesh configuration from repository manifests and tracks istioctl commands in CI.

## Overview

This collector finds Istio custom resources committed to a repository and extracts the service-mesh posture: mTLS mode from PeerAuthentication, AuthorizationPolicy actions, JWT RequestAuthentication, and traffic resources (VirtualService, DestinationRule, Gateway, ServiceEntry, Sidecar). It also records sidecar-injection settings, Telemetry config, and the IstioOperator install profile, validating each resource offline with `istioctl analyze`. During CI it intercepts `istioctl` commands so mesh operations are recorded alongside the config. Data is written to the tool-agnostic `.mesh` category so guardrails work regardless of mesh implementation.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.mesh.source` | object | Tool metadata (tool name and version) |
| `.mesh.provider` | string | Mesh implementation (`istio`) |
| `.mesh.resources[]` | array | Every Istio resource found (`kind`, `name`, `namespace`, `path`, `valid`) |
| `.mesh.peer_authentications[]` | array | PeerAuthentication resources (`scope`, `mode`) |
| `.mesh.authorization_policies[]` | array | AuthorizationPolicy resources (`action`, `rule_count`, `allows_all`) |
| `.mesh.request_authentications[]` | array | RequestAuthentication (JWT) resources (`issuers`) |
| `.mesh.virtual_services[]` | array | VirtualService routing (`hosts`, `has_timeout`, `has_retries`) |
| `.mesh.destination_rules[]` | array | DestinationRule traffic policy (`tls_mode`, `has_outlier_detection`) |
| `.mesh.gateways[]` | array | Gateway servers (`port`, `protocol`, `tls_mode`, `https_redirect`) |
| `.mesh.service_entries[]` | array | ServiceEntry external hosts (`location`, `resolution`) |
| `.mesh.sidecars[]` | array | Sidecar egress scope (`restricts_egress`, `egress_hosts`) |
| `.mesh.envoy_filters[]` | array | EnvoyFilter resources (`name`, `namespace`) |
| `.mesh.telemetry[]` | array | Telemetry config (`has_tracing`, `has_metrics`, `has_access_logging`) |
| `.mesh.install[]` | array | IstioOperator install (`profile`) |
| `.mesh.injection` | object | Namespace injection labels + per-workload inject overrides |
| `.mesh.cicd` | object | istioctl CI command tracking (commands + client version) |
| `.mesh.summary` | object | Derived posture booleans (`mtls_strict`, `all_gateways_tls`, etc.) |

The collector reads config from the repository, not a live cluster (like the `k8s` collector); `istioctl analyze` runs with `--use-kube=false` so no cluster credentials are required. If no Istio resources are found it writes nothing, so downstream policies skip cleanly on non-mesh components.

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `istio` | Parses Istio custom resources (traffic, security, telemetry, install, injection) |
| `cicd` | Tracks all istioctl commands executed in CI pipelines (install, analyze, upgrade) |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/istio@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [kubernetes, mesh]
    # with:
    #   find_command: "find ./istio -name '*.yaml'"  # Custom find command
```
