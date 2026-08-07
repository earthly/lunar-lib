# Istio Guardrails

Enforces Istio service-mesh security and traffic best practices.

## Overview

This policy validates Istio service-mesh configuration against production best practices: STRICT mutual TLS, an authorization baseline, no accidental allow-all rules, TLS on ingress gateways, and sidecar injection on mesh namespaces. It reads the normalized `.mesh` data produced by the `istio` collector, so the checks describe mesh posture rather than tool internals. It helps ensure a mesh actually enforces the encryption and access control it was adopted for, instead of quietly running in permissive mode.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `valid` | Validates Istio resources parse and pass `istioctl analyze` |
| `mtls-strict` | Requires mesh-wide mTLS in STRICT mode |
| `authorization-policies-defined` | Requires at least one AuthorizationPolicy |
| `no-permissive-authz` | Forbids blanket allow-all AuthorizationPolicy rules |
| `gateway-tls` | Requires ingress Gateways to use TLS / redirect HTTP |
| `sidecar-injection` | Requires mesh namespaces to enable sidecar injection |
| `no-envoy-filter` | Advisory: flags brittle EnvoyFilter usage |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.mesh.resources[]` | array | `istio` collector |
| `.mesh.peer_authentications[]` | array | `istio` collector |
| `.mesh.authorization_policies[]` | array | `istio` collector |
| `.mesh.gateways[]` | array | `istio` collector |
| `.mesh.envoy_filters[]` | array | `istio` collector |
| `.mesh.injection` | object | `istio` collector |
| `.mesh.summary` | object | `istio` collector |

**Note:** Ensure the `istio` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/istio@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [kubernetes, mesh]
    enforcement: report-pr
    # include: [mtls-strict, gateway-tls]  # Only run specific checks
    # with:
    #   required_mtls_mode: "STRICT"
```

## Examples

### Passing Example

A component with STRICT mesh mTLS, an authorization policy, and injection enabled:

```json
{
  "mesh": {
    "peer_authentications": [
      {"name": "default", "namespace": "istio-system", "scope": "mesh", "mode": "STRICT"}
    ],
    "authorization_policies": [
      {"name": "require-jwt", "namespace": "bookinfo", "action": "ALLOW", "rule_count": 1, "allows_all": false}
    ],
    "gateways": [
      {"name": "ingress", "namespace": "istio-system", "servers": [{"port": 443, "protocol": "HTTPS", "tls_mode": "SIMPLE"}]}
    ],
    "injection": {
      "namespaces": [{"name": "bookinfo", "enabled": true}],
      "workload_overrides": []
    },
    "summary": {"mtls_strict": true, "has_authorization_policies": true, "all_gateways_tls": true, "injection_enabled": true}
  }
}
```

### Failing Example

A component running permissive mTLS, no authorization, and a plaintext gateway:

```json
{
  "mesh": {
    "peer_authentications": [
      {"name": "default", "namespace": "istio-system", "scope": "mesh", "mode": "PERMISSIVE"}
    ],
    "authorization_policies": [],
    "gateways": [
      {"name": "ingress", "namespace": "istio-system", "servers": [{"port": 80, "protocol": "HTTP", "https_redirect": false}]}
    ],
    "injection": {
      "namespaces": [{"name": "bookinfo", "enabled": false}],
      "workload_overrides": [{"kind": "Deployment", "name": "api", "namespace": "bookinfo", "inject": false}]
    },
    "summary": {"mtls_strict": false, "has_authorization_policies": false, "all_gateways_tls": false, "injection_enabled": false}
  }
}
```

**Failure messages:**
- `Mesh mTLS is PERMISSIVE — set a mesh-wide PeerAuthentication with mode: STRICT`
- `No AuthorizationPolicy defined — mTLS authenticates workloads but does not authorize them`
- `Gateway istio-system/ingress server on port 80 serves plaintext — set httpsRedirect: true or use TLS`
- `Namespace bookinfo runs mesh workloads but sidecar injection is not enabled`

## Remediation

When this policy fails, resolve it by:

1. **For `valid` failures:** Fix the Istio resource flagged by `istioctl analyze` (bad host, missing subset, malformed selector).
2. **For `mtls-strict` failures:** Create a `PeerAuthentication` named `default` in the Istio root namespace (usually `istio-system`) with `spec.mtls.mode: STRICT`, and remove any PERMISSIVE/DISABLE overrides. Workloads that must accept plaintext (e.g. during migration) can be scoped out via `include`/`exclude` in `lunar-config.yml`.
3. **For `authorization-policies-defined` failures:** Add an `AuthorizationPolicy` — start with a namespace default-deny (`{}`) plus explicit ALLOW rules for expected callers.
4. **For `no-permissive-authz` failures:** Add `from`/`to`/`when` constraints to the flagged ALLOW rule so it no longer matches every source, or split it into scoped rules.
5. **For `gateway-tls` failures:** Add a `tls` block to HTTPS/TLS `Gateway` servers, and set `tls.httpsRedirect: true` on plain HTTP servers so ingress never serves plaintext.
6. **For `sidecar-injection` failures:** Label the namespace with `istio-injection=enabled` (or the revision label `istio.io/rev=<rev>`), and remove `sidecar.istio.io/inject: "false"` from workloads that should join the mesh.
7. **For `no-envoy-filter` (advisory):** Review each `EnvoyFilter`; migrate to a supported Istio API where possible, or accept the upgrade risk. Pin `enforcement: report-pr` to keep it non-blocking.
