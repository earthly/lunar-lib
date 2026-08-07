# aggregate.jq — merge per-file chunks into the final .mesh object.
# Input: {chunks: [<parse.jq output>...], validity: {<path>: <error message>}}
# Output: the .mesh object (minus .source, which main.sh adds separately).

.chunks as $chunks
| .validity as $validity
| {
    provider: "istio",
    resources: [ $chunks[].resources[]
        | if ($validity[.path] != null)
          then (.valid = false) + {error: $validity[.path]}
          else . end ],
    peer_authentications: [ $chunks[].peer_authentications[] ],
    authorization_policies: [ $chunks[].authorization_policies[] ],
    request_authentications: [ $chunks[].request_authentications[] ],
    virtual_services: [ $chunks[].virtual_services[] ],
    destination_rules: [ $chunks[].destination_rules[] ],
    gateways: [ $chunks[].gateways[] ],
    service_entries: [ $chunks[].service_entries[] ],
    sidecars: [ $chunks[].sidecars[] ],
    envoy_filters: [ $chunks[].envoy_filters[] ],
    telemetry: [ $chunks[].telemetry[] ],
    install: [ $chunks[].install[] ],
    injection: {
      namespaces: [ $chunks[].injection_namespaces[] ],
      workload_overrides: [ $chunks[].workload_overrides[] ]
    }
  }
| . as $m
| ([ $m.peer_authentications[] | select(.scope == "mesh") | .mode ] | (.[0] // null)) as $default_mode
| .summary = {
    mtls_default_mode: $default_mode,
    mtls_strict: ($default_mode == "STRICT"
                  and ($m.peer_authentications | any(.mode == "PERMISSIVE") | not)
                  and ($m.peer_authentications | any(.mode == "DISABLE") | not)),
    has_authorization_policies: (($m.authorization_policies | length) > 0),
    all_gateways_tls: ([ $m.gateways[].servers[] ] | all((.tls_mode != null) or (.https_redirect == true))),
    injection_enabled: ($m.injection.namespaces | any(.enabled == true)),
    uses_envoy_filters: (($m.envoy_filters | length) > 0)
  }
