# parse.jq — extract Istio resources from one manifest file.
# Input: the array of YAML documents parsed from a single file.
# Arg:   $path (the file path, for provenance).
# Output: a single object with one array per Istio resource type, plus
#         injection data and an `istio_signal` count used to decide whether
#         the file contributes any mesh data at all.

# Istio API groups — matches networking/security/telemetry/install/extensions.
def is_istio: ((.apiVersion // "") | test("(networking|security|telemetry|install|extensions)\\.istio\\.io"));
def nm: (.metadata.name // "<unknown>");
def ns: (.metadata.namespace // "default");
def kindmatch($re): ((.kind // "") | test($re));

# Drop null / non-object documents (empty YAML docs parse to null).
[ .[] | select(. != null and (type == "object")) ] as $docs
| {
    resources: [ $docs[] | select(is_istio) | {kind: .kind, name: nm, namespace: ns, path: $path, valid: true} ],

    peer_authentications: [ $docs[] | select(.kind == "PeerAuthentication") | {
        name: nm, namespace: ns, path: $path,
        mode: (.spec.mtls.mode // null),
        scope: (if (.spec.selector != null) then "workload"
                elif (ns == "istio-system") then "mesh"
                else "namespace" end)
      } ],

    authorization_policies: [ $docs[] | select(.kind == "AuthorizationPolicy")
        | (.spec.action // "ALLOW") as $action
        | (.spec.rules // []) as $rules
        | {
            name: nm, namespace: ns, path: $path,
            action: $action,
            rule_count: ($rules | length),
            allows_all: (($action == "ALLOW")
                         and (($rules | length) > 0)
                         and ($rules | any((.from == null) and (.to == null) and (.when == null))))
          } ],

    request_authentications: [ $docs[] | select(.kind == "RequestAuthentication") | {
        name: nm, namespace: ns, path: $path,
        issuers: [ (.spec.jwtRules // [])[] | .issuer // empty ]
      } ],

    virtual_services: [ $docs[] | select(.kind == "VirtualService") | {
        name: nm, namespace: ns, path: $path,
        hosts: (.spec.hosts // []),
        gateways: (.spec.gateways // []),
        has_timeout: ((.spec.http // []) | any(.timeout != null)),
        has_retries: ((.spec.http // []) | any(.retries != null)),
        has_fault_injection: ((.spec.http // []) | any(.fault != null))
      } ],

    destination_rules: [ $docs[] | select(.kind == "DestinationRule") | {
        name: nm, namespace: ns, path: $path,
        host: (.spec.host // null),
        tls_mode: (.spec.trafficPolicy.tls.mode // null),
        has_outlier_detection: (.spec.trafficPolicy.outlierDetection != null),
        has_connection_pool: (.spec.trafficPolicy.connectionPool != null),
        subsets: [ (.spec.subsets // [])[] | .name // empty ]
      } ],

    gateways: [ $docs[] | select(.kind == "Gateway") | {
        name: nm, namespace: ns, path: $path,
        servers: [ (.spec.servers // [])[] | {
            port: (.port.number // null),
            protocol: (.port.protocol // null),
            tls_mode: (.tls.mode // null),
            https_redirect: (.tls.httpsRedirect // false)
          } ]
      } ],

    service_entries: [ $docs[] | select(.kind == "ServiceEntry") | {
        name: nm, namespace: ns, path: $path,
        hosts: (.spec.hosts // []),
        location: (.spec.location // null),
        resolution: (.spec.resolution // null)
      } ],

    sidecars: [ $docs[] | select(.kind == "Sidecar")
        | ([ (.spec.egress // [])[] | (.hosts // [])[] ]) as $eg
        | {
            name: nm, namespace: ns, path: $path,
            egress_hosts: $eg,
            restricts_egress: (($eg | length) > 0 and ($eg | any(. == "*/*") | not))
          } ],

    envoy_filters: [ $docs[] | select(.kind == "EnvoyFilter") | {name: nm, namespace: ns, path: $path} ],

    telemetry: [ $docs[] | select(.kind == "Telemetry") | {
        name: nm, namespace: ns, path: $path,
        has_tracing: (.spec.tracing != null),
        has_metrics: (.spec.metrics != null),
        has_access_logging: (.spec.accessLogging != null)
      } ],

    install: [ $docs[] | select(.kind == "IstioOperator") | {
        kind: "IstioOperator", name: nm, namespace: ns, path: $path,
        profile: (.spec.profile // "default")
      } ],

    injection_namespaces: [ $docs[] | select(.kind == "Namespace")
        | (.metadata.labels // {}) as $l
        | select(($l["istio-injection"] != null) or ($l["istio.io/rev"] != null))
        | {
            name: nm, path: $path,
            enabled: (($l["istio-injection"] == "enabled") or ($l["istio.io/rev"] != null)),
            revision: ($l["istio.io/rev"] // null)
          } ],

    workload_overrides: [ $docs[] | select(kindmatch("^(Deployment|StatefulSet|DaemonSet|Job|CronJob|ReplicaSet|Pod|Rollout)$"))
        | (if .kind == "CronJob" then .spec.jobTemplate.spec.template
           elif .kind == "Pod" then .
           else .spec.template end) as $tmpl
        | (($tmpl // {}).metadata.annotations // {}) as $ann
        | select($ann["sidecar.istio.io/inject"] != null)
        | {
            kind: .kind, name: nm, namespace: ns, path: $path,
            inject: ($ann["sidecar.istio.io/inject"] == "true")
          } ]
  }
| . + { istio_signal: ((.resources | length) + (.injection_namespaces | length) + (.workload_overrides | length)) }
