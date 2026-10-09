# Extracts the .k8s entries from an array of Kubernetes objects. Shared by
# main.sh (static manifests) and render.sh (Helm renders) so both record the
# same shape. Each object carries the file or chart template it came from in
# `__path`. $render is null for a static manifest; for a chart render it is
# {chart, values} and is copied onto every entry.
#
# Effective values are recorded: unset fields take the Kubernetes default.

def render_key: if $render == null then {} else {render: $render} end;

def or_default($d): if . == null then $d else . end;

# Unset (or zero, which the API server defaults the same way) probe timings.
def positive($d): if (. // 0) > 0 then . else $d end;

def probe:
  if . == null then null else
    (if .httpGet then "httpGet" elif .tcpSocket then "tcpSocket"
     elif .grpc then "grpc" elif .exec then "exec" else null end) as $handler
    | {
        handler: $handler,
        port: (.httpGet.port // .tcpSocket.port // .grpc.port // null),
        path: (if $handler == "httpGet" then (.httpGet.path // "/") else null end),
        initial_delay_seconds: (.initialDelaySeconds | or_default(0)),
        period_seconds: (.periodSeconds | positive(10)),
        timeout_seconds: (.timeoutSeconds | positive(1)),
        failure_threshold: (.failureThreshold | positive(3))
      }
      + (if $handler == "exec" then {command: (.exec.command // [])} else {} end)
      + (if $handler == "grpc" then {service: (.grpc.service // "")} else {} end)
  end;

def container($pod):
  {
    name: .name,
    image: (.image // null),
    has_resources: ((.resources.requests != null) or (.resources.limits != null)),
    has_requests: (.resources.requests != null),
    has_limits: (.resources.limits != null),
    cpu_request: (.resources.requests.cpu // null),
    cpu_limit: (.resources.limits.cpu // null),
    memory_request: (.resources.requests.memory // null),
    memory_limit: (.resources.limits.memory // null),
    has_liveness_probe: (.livenessProbe != null),
    has_readiness_probe: (.readinessProbe != null),
    liveness_probe: (.livenessProbe | probe),
    readiness_probe: (.readinessProbe | probe),
    startup_probe: (.startupProbe | probe),
    has_prestop: (.lifecycle.preStop != null),
    runs_as_non_root: (if .securityContext.runAsNonRoot == null then (($pod.securityContext.runAsNonRoot == true) // false) else (.securityContext.runAsNonRoot == true) end),
    read_only_root_fs: ((.securityContext.readOnlyRootFilesystem == true) // false),
    privileged: ((.securityContext.privileged == true) // false)
  };

def workload:
  (if .kind == "CronJob" then .spec.jobTemplate.spec.template else .spec.template end // {}) as $template
  | ($template.spec // {}) as $pod
  | {kind: .kind, name: .metadata.name, namespace: (.metadata.namespace // "default"), path: .__path}
  + render_key
  + {
      replicas: (.spec.replicas | or_default(1)),
      replicas_set: (.spec.replicas != null),
      # Pod template labels: what a PodDisruptionBudget selector matches.
      pod_labels: ($template.metadata.labels // {}),
      pod_annotations: ($template.metadata.annotations // {}),
      host_users: ($pod.hostUsers | or_default(true)),
      host_network: ($pod.hostNetwork | or_default(false)),
      host_pid: ($pod.hostPID | or_default(false)),
      host_ipc: ($pod.hostIPC | or_default(false)),
      termination_grace_period_seconds: ($pod.terminationGracePeriodSeconds | or_default(30)),
      topology_spread_constraints: [($pod.topologySpreadConstraints // [])[] | {
        topology_key: .topologyKey,
        max_skew: .maxSkew,
        when_unsatisfiable: (.whenUnsatisfiable // "DoNotSchedule"),
        label_selector: (.labelSelector // null),
        match_label_keys: (.matchLabelKeys // [])
      }],
      containers: [($pod.containers // [])[] | container($pod)],
      init_containers: [($pod.initContainers // [])[] | container($pod)]
    };

def entry: {name: .metadata.name, namespace: (.metadata.namespace // "default"), path: .__path} + render_key;

map(select(type == "object" and .kind != null)) as $docs
| {
    resources: [$docs[] | {kind: .kind, name: .metadata.name, namespace: (.metadata.namespace // "default"), api_version: (.apiVersion // null)}],
    workloads: [$docs[] | select(.kind | test($kinds)) | workload],
    pdbs: [$docs[] | select(.kind == "PodDisruptionBudget") | entry + {
      # The full LabelSelector (matchLabels + matchExpressions); the pdb
      # policy matches it against the pod_labels of each workload.
      selector: (.spec.selector // null),
      # Deprecated guess at the name of the covered workload; kept for
      # one release so existing consumers keep working.
      target_workload: (.spec.selector.matchLabels.app // .spec.selector.matchLabels["app.kubernetes.io/name"] // null),
      min_available: (.spec.minAvailable // null),
      max_unavailable: (.spec.maxUnavailable // null)
    }],
    hpas: [$docs[] | select(.kind == "HorizontalPodAutoscaler") | entry + {
      target_workload: .spec.scaleTargetRef.name,
      target_kind: (.spec.scaleTargetRef.kind // null),
      min_replicas: (.spec.minReplicas // 1),
      max_replicas: .spec.maxReplicas
    }],
    # KEDA defaults: minReplicaCount 0, maxReplicaCount 100, and a Deployment target.
    scaled_objects: [$docs[] | select(.kind == "ScaledObject" and ((.apiVersion // "") | startswith("keda.sh/"))) | entry + {
      target_workload: .spec.scaleTargetRef.name,
      target_kind: (.spec.scaleTargetRef.kind // "Deployment"),
      min_replicas: (.spec.minReplicaCount | or_default(0)),
      max_replicas: (.spec.maxReplicaCount | or_default(100))
    }],
    # The apiVersion filter keeps out Calico's projectcalico.org
    # NetworkPolicy, which shares the kind but not the schema.
    network_policies: [$docs[] | select(.kind == "NetworkPolicy" and ((.apiVersion // "") | startswith("networking.k8s.io/"))) | entry + {
      # An absent podSelector is the empty selector: every pod in the namespace.
      pod_selector: (.spec.podSelector // {}),
      # Effective policyTypes: when unset, the API server applies Ingress, plus
      # Egress only if the policy has at least one egress rule.
      policy_types: (
        if ((.spec.policyTypes // []) | length) > 0 then .spec.policyTypes
        else ["Ingress"] + (if ((.spec.egress // []) | length) > 0 then ["Egress"] else [] end)
        end
      ),
      egress: (.spec.egress // [])
    }]
  }
