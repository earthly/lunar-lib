# Deployment and Infrastructure Guardrails

This document specifies possible policies for the **Deployment and Infrastructure** category. These guardrails cover Kubernetes workload configuration, Infrastructure as Code (Terraform/Pulumi), CD pipeline requirements, container image standards, encryption, and deployment lifecycle management.

---

## Kubernetes Workload Configuration

### Resource Management

* `k8s-container-has-cpu-memory-requests` **Containers define CPU and memory requests**: All containers in Kubernetes workloads must specify CPU and memory resource requests for proper scheduling.
  * Collector(s): Parse Kubernetes manifests (Deployments, StatefulSets, DaemonSets, Jobs) and extract container resource specifications
  * Component JSON:
    * `.k8s.workloads[].containers[].has_requests` - Boolean indicating resource requests are defined
    * `.k8s.workloads[].containers[].cpu_request` - CPU request value
    * `.k8s.workloads[].containers[].memory_request` - Memory request value
    * `.k8s.summary.all_have_requests` - Boolean indicating all containers have requests
  * Policy: Assert that all containers have CPU and memory requests defined
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-container-has-cpu-memory-limits` **Containers define CPU and memory limits**: All containers must specify CPU and memory limits to prevent resource exhaustion.
  * Collector(s): Parse Kubernetes manifests and extract container resource limits
  * Component JSON:
    * `.k8s.workloads[].containers[].has_limits` - Boolean indicating resource limits are defined
    * `.k8s.workloads[].containers[].cpu_limit` - CPU limit value
    * `.k8s.workloads[].containers[].memory_limit` - Memory limit value
    * `.k8s.summary.all_have_limits` - Boolean indicating all containers have limits
  * Policy: Assert that all containers have CPU and memory limits defined
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-resources-within-range` **Resource requests and limits are within acceptable range**: Resource specifications should not be excessively high or impractically low.
  * Collector(s): Parse resource values and convert to normalized units for comparison
  * Component JSON:
    * `.k8s.workloads[].containers[].cpu_request` - CPU request value
    * `.k8s.workloads[].containers[].cpu_limit` - CPU limit value
    * `.k8s.workloads[].containers[].memory_request` - Memory request value
    * `.k8s.workloads[].containers[].memory_limit` - Memory limit value
  * Policy: Assert that resource values fall within configured minimum and maximum ranges
  * Configuration: Min/max CPU requests (default: 10m-4), min/max memory requests (default: 32Mi-8Gi)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-cpu-limit-request-ratio` **CPU limit-to-request ratio is reasonable**: The ratio between CPU limits and requests should not be excessive to prevent resource contention.
  * Collector(s): Calculate ratio between CPU limit and request for each container
  * Component JSON:
    * `.k8s.workloads[].containers[].cpu_limit_request_ratio` - Ratio of limit to request
  * Policy: Assert that CPU limit-to-request ratio does not exceed configured maximum
  * Configuration: Maximum ratio (default: 10)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### High Availability

* `k8s-minimum-replica-count` **Deployments have minimum replica count**: Production workloads must have a minimum number of replicas for high availability.
  * Collector(s): Parse Kubernetes Deployments and StatefulSets for replica count
  * Component JSON:
    * `.k8s.workloads[].replicas` - Configured replica count
    * `.k8s.workloads[].kind` - Workload kind (Deployment, StatefulSet)
    * `.k8s.workloads[].name` - Workload name
  * Policy: Assert that replica count meets or exceeds the configured minimum for production workloads
  * Configuration: Minimum replicas (default: 3), tags requiring minimum replicas (e.g., ["production", "tier1"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-pdb-exists` **Pod Disruption Budget exists for workloads**: Production workloads must have a PodDisruptionBudget to ensure availability during node maintenance.
  * Collector(s): Parse Kubernetes manifests for PDBs and correlate with workloads by label selectors
  * Component JSON:
    * `.k8s.pdbs[]` - Array of PodDisruptionBudget configurations
    * `.k8s.pdbs[].target_workload` - Workload the PDB applies to
    * `.k8s.pdbs[].min_available` - Minimum available pods
    * `.k8s.pdbs[].max_unavailable` - Maximum unavailable pods
    * `.k8s.summary.all_have_pdb` - Boolean indicating all workloads have PDBs
  * Policy: Assert that all production workloads have an associated PodDisruptionBudget
  * Configuration: Tags requiring PDB (e.g., ["production", "tier1", "tier2"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-pdb-appropriate-settings` **Pod Disruption Budget has appropriate settings**: PDB minimum availability should ensure at least one pod remains during disruptions.
  * Collector(s): Parse PDB specifications and validate settings
  * Component JSON:
    * `.k8s.pdbs[].min_available` - Minimum available pods (absolute or percentage)
    * `.k8s.pdbs[].max_unavailable` - Maximum unavailable pods
  * Policy: Assert that PDB allows at least one pod to remain available
  * Configuration: Minimum availability threshold (default: 1 or 50%)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-hpa-configured` **Horizontal Pod Autoscaler is configured**: Production workloads should have HPA for automatic scaling based on load.
  * Collector(s): Parse Kubernetes manifests for HPAs and correlate with workloads
  * Component JSON:
    * `.k8s.hpas[]` - Array of HPA configurations
    * `.k8s.hpas[].target_workload` - Workload the HPA targets
    * `.k8s.hpas[].min_replicas` - Minimum replica count
    * `.k8s.hpas[].max_replicas` - Maximum replica count
    * `.k8s.summary.all_have_hpa` - Boolean indicating all workloads have HPA
  * Policy: Assert that production workloads have an associated HPA
  * Configuration: Tags requiring HPA (e.g., ["production", "auto-scaling"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-hpa-min-replicas` **HPA minimum replicas meet availability requirements**: HPA minReplicas should not be set below the high availability threshold.
  * Collector(s): Parse HPA specifications for minimum replica settings
  * Component JSON:
    * `.k8s.hpas[].min_replicas` - HPA minimum replicas
    * `.k8s.hpas[].target_workload` - Target workload name
  * Policy: Assert that HPA minReplicas is at least the configured minimum
  * Configuration: Minimum HPA replicas (default: 3)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Health Probes

* `k8s-container-has-liveness-probe` **Containers have liveness probes configured**: All containers must have liveness probes to detect and recover from stuck processes.
  * Collector(s): Parse Kubernetes manifests for container liveness probe configurations
  * Component JSON:
    * `.k8s.workloads[].containers[].has_liveness_probe` - Boolean indicating liveness probe is defined
    * `.k8s.workloads[].containers[].liveness_probe` - Probe configuration details
    * `.k8s.summary.all_have_liveness_probes` - Boolean for all containers
  * Policy: Assert that all containers have liveness probes defined
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-container-has-readiness-probe` **Containers have readiness probes configured**: All containers must have readiness probes to ensure traffic is only sent to ready pods.
  * Collector(s): Parse Kubernetes manifests for container readiness probe configurations
  * Component JSON:
    * `.k8s.workloads[].containers[].has_readiness_probe` - Boolean indicating readiness probe is defined
    * `.k8s.workloads[].containers[].readiness_probe` - Probe configuration details
    * `.k8s.summary.all_have_readiness_probes` - Boolean for all containers
  * Policy: Assert that all containers have readiness probes defined
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-container-has-startup-probe` **Containers have startup probes for slow-starting applications**: Applications with long initialization times should use startup probes to prevent premature kills.
  * Collector(s): Parse Kubernetes manifests for startup probe configurations
  * Component JSON:
    * `.k8s.workloads[].containers[].has_startup_probe` - Boolean indicating startup probe is defined
    * `.k8s.workloads[].containers[].startup_probe` - Probe configuration details
  * Policy: Assert that containers tagged for slow startup have startup probes
  * Configuration: Tags requiring startup probes (e.g., ["slow-start", "jvm", "heavy-init"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-probe-initial-delay-configured` **Probe initial delay is appropriately configured**: Probe initialDelaySeconds should allow sufficient time for application startup.
  * Collector(s): Extract probe timing configuration from manifests
  * Component JSON:
    * `.k8s.workloads[].containers[].liveness_probe.initial_delay_seconds` - Liveness probe delay
    * `.k8s.workloads[].containers[].readiness_probe.initial_delay_seconds` - Readiness probe delay
  * Policy: Assert that probe delays are within acceptable ranges
  * Configuration: Minimum/maximum initial delay (default: 5-300 seconds)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Container Security

* `k8s-container-non-root` **Containers run as non-root user**: Containers must not run as the root user to minimize security risk.
  * Collector(s): Parse Kubernetes manifests for securityContext settings at pod and container level
  * Component JSON:
    * `.k8s.workloads[].containers[].runs_as_non_root` - Boolean indicating non-root execution
    * `.k8s.workloads[].containers[].run_as_user` - Numeric UID if specified
    * `.k8s.summary.all_non_root` - Boolean indicating all containers run as non-root
  * Policy: Assert that all containers run as non-root
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-container-read-only-root-fs` **Containers have read-only root filesystem**: Containers should use read-only root filesystem to prevent runtime modifications.
  * Collector(s): Parse securityContext for readOnlyRootFilesystem setting
  * Component JSON:
    * `.k8s.workloads[].containers[].read_only_root_fs` - Boolean indicating read-only filesystem
    * `.k8s.summary.all_read_only_root_fs` - Boolean for all containers
  * Policy: Assert that all containers have read-only root filesystem enabled
  * Configuration: Exclusion patterns for containers that legitimately need write access
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-container-no-privileged` **Containers do not run in privileged mode**: Containers must not be granted privileged mode as it provides full host access.
  * Collector(s): Parse securityContext for privileged setting
  * Component JSON:
    * `.k8s.workloads[].containers[].privileged` - Boolean indicating privileged mode
    * `.k8s.summary.none_privileged` - Boolean indicating no containers are privileged
  * Policy: Assert that no containers run in privileged mode
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-container-no-privilege-escalation` **Containers do not allow privilege escalation**: Containers must have allowPrivilegeEscalation set to false.
  * Collector(s): Parse securityContext for allowPrivilegeEscalation setting
  * Component JSON:
    * `.k8s.workloads[].containers[].allow_privilege_escalation` - Boolean for privilege escalation
    * `.k8s.summary.none_allow_escalation` - Boolean for all containers
  * Policy: Assert that no containers allow privilege escalation
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-container-drops-all-capabilities` **Containers drop all capabilities**: Containers should drop all Linux capabilities and add only required ones explicitly.
  * Collector(s): Parse securityContext for capabilities configuration
  * Component JSON:
    * `.k8s.workloads[].containers[].capabilities_dropped` - Array of dropped capabilities
    * `.k8s.workloads[].containers[].capabilities_added` - Array of added capabilities
    * `.k8s.workloads[].containers[].drops_all_capabilities` - Boolean indicating ALL are dropped
  * Policy: Assert that containers drop ALL capabilities
  * Configuration: Allowed capabilities to add back if needed
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-container-no-dangerous-capabilities` **Containers do not add dangerous capabilities**: Containers must not add dangerous Linux capabilities like NET_ADMIN, SYS_ADMIN.
  * Collector(s): Parse securityContext for added capabilities
  * Component JSON:
    * `.k8s.workloads[].containers[].capabilities_added` - Array of added capabilities
    * `.k8s.workloads[].containers[].has_dangerous_capabilities` - Boolean for dangerous caps
  * Policy: Assert that no dangerous capabilities are added
  * Configuration: List of forbidden capabilities (default: ["NET_ADMIN", "SYS_ADMIN", "SYS_PTRACE", "ALL"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-pod-security-context` **Pod security context enforces security standards**: Pod-level securityContext should enforce runAsNonRoot and fsGroup settings.
  * Collector(s): Parse pod-level securityContext from workload specifications
  * Component JSON:
    * `.k8s.workloads[].pod_security_context.run_as_non_root` - Pod-level non-root setting
    * `.k8s.workloads[].pod_security_context.fs_group` - Filesystem group setting
    * `.k8s.workloads[].pod_security_context.seccomp_profile` - Seccomp profile type
  * Policy: Assert that pod security context enforces expected security controls
  * Configuration: Required pod security context settings
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-container-seccomp-profile` **Containers use seccomp profiles**: Containers should use RuntimeDefault or custom seccomp profiles to restrict syscalls.
  * Collector(s): Parse securityContext for seccompProfile settings
  * Component JSON:
    * `.k8s.workloads[].containers[].seccomp_profile_type` - Seccomp profile type
    * `.k8s.summary.all_have_seccomp` - Boolean for all containers
  * Policy: Assert that containers specify a seccomp profile
  * Configuration: Acceptable profile types (default: ["RuntimeDefault", "Localhost"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Host Isolation (OPA/Gatekeeper PSP Policies)

* `k8s-no-host-pid` **Pods do not share host PID namespace**: Pods must not use hostPID to prevent process visibility across the host.
  * Collector(s): Parse pod specifications for hostPID setting
  * Component JSON:
    * `.k8s.workloads[].host_pid` - Boolean indicating hostPID usage
    * `.k8s.summary.none_use_host_pid` - Boolean for all workloads
  * Policy: Assert that no pods use hostPID
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-no-host-ipc` **Pods do not share host IPC namespace**: Pods must not use hostIPC to prevent inter-process communication with host processes.
  * Collector(s): Parse pod specifications for hostIPC setting
  * Component JSON:
    * `.k8s.workloads[].host_ipc` - Boolean indicating hostIPC usage
    * `.k8s.summary.none_use_host_ipc` - Boolean for all workloads
  * Policy: Assert that no pods use hostIPC
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-no-host-network` **Pods do not use host networking**: Pods must not use hostNetwork to prevent access to host network interfaces.
  * Collector(s): Parse pod specifications for hostNetwork setting
  * Component JSON:
    * `.k8s.workloads[].host_network` - Boolean indicating hostNetwork usage
    * `.k8s.summary.none_use_host_network` - Boolean for all workloads
  * Policy: Assert that no pods use hostNetwork
  * Configuration: Exceptions for specific system components if needed
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-no-host-ports` **Pods do not bind to host ports**: Containers should not bind directly to host ports, which bypasses network policies.
  * Collector(s): Parse container port specifications for hostPort usage
  * Component JSON:
    * `.k8s.workloads[].containers[].host_ports` - Array of host ports used
    * `.k8s.workloads[].uses_host_ports` - Boolean indicating any hostPort usage
    * `.k8s.summary.none_use_host_ports` - Boolean for all workloads
  * Policy: Assert that no containers use host ports (or only allowed ports)
  * Configuration: Allowed host port ranges if exceptions needed
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-allowed-volume-types` **Pods use only allowed volume types**: Pods should only use approved volume types to limit attack surface.
  * Collector(s): Parse pod volume specifications and extract volume types
  * Component JSON:
    * `.k8s.workloads[].volume_types` - Array of volume types used (configMap, secret, emptyDir, persistentVolumeClaim, etc.)
    * `.k8s.workloads[].has_forbidden_volume_types` - Boolean for forbidden types
    * `.k8s.workloads[].forbidden_volumes` - Array of volumes using forbidden types
  * Policy: Assert that only allowed volume types are used
  * Configuration: Allowed volume types (default: ["configMap", "secret", "emptyDir", "persistentVolumeClaim", "downwardAPI", "projected"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-hostpath-restricted` **HostPath volumes are restricted**: HostPath volumes must be limited to specific paths and mounted read-only.
  * Collector(s): Parse pod volume specifications for hostPath volumes
  * Component JSON:
    * `.k8s.workloads[].hostpath_volumes[].path` - Host path being mounted
    * `.k8s.workloads[].hostpath_volumes[].read_only` - Boolean for read-only mount
    * `.k8s.workloads[].hostpath_volumes[].is_allowed_path` - Boolean for allowed path
    * `.k8s.summary.hostpaths_compliant` - Boolean for all hostPath compliance
  * Policy: Assert that hostPath volumes use allowed paths and are read-only
  * Configuration: Allowed hostPath prefixes (e.g., ["/var/log", "/tmp"]), require read-only
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-flexvolume-approved` **FlexVolume drivers are from approved list**: FlexVolume drivers must be from organization-approved list.
  * Collector(s): Parse pod volume specifications for flexVolume drivers
  * Component JSON:
    * `.k8s.workloads[].flexvolume_drivers` - Array of FlexVolume drivers used
    * `.k8s.workloads[].has_unapproved_flexvolumes` - Boolean for unapproved drivers
  * Policy: Assert that only approved FlexVolume drivers are used
  * Configuration: Approved FlexVolume driver list
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-emptydir-size-limit` **EmptyDir volumes have size limits**: EmptyDir volumes must specify sizeLimit to prevent disk exhaustion.
  * Collector(s): Parse pod volume specifications for emptyDir without sizeLimit
  * Component JSON:
    * `.k8s.workloads[].emptydir_volumes[].name` - Volume name
    * `.k8s.workloads[].emptydir_volumes[].size_limit` - Configured size limit
    * `.k8s.workloads[].emptydir_volumes[].has_size_limit` - Boolean for limit presence
    * `.k8s.summary.all_emptydir_have_limits` - Boolean for all emptyDir volumes
  * Policy: Assert that all emptyDir volumes specify a sizeLimit
  * Configuration: Maximum allowed size limit (default: 1Gi)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Linux Security Modules (OPA/Gatekeeper PSP Policies)

* `k8s-apparmor-profile` **Pods specify AppArmor profiles**: Pods should use AppArmor profiles to restrict container capabilities.
  * Collector(s): Parse pod annotations for AppArmor profile specifications
  * Component JSON:
    * `.k8s.workloads[].containers[].apparmor_profile` - AppArmor profile name
    * `.k8s.workloads[].containers[].has_apparmor` - Boolean for AppArmor annotation
    * `.k8s.summary.all_have_apparmor` - Boolean for all containers
  * Policy: Assert that containers specify AppArmor profiles
  * Configuration: Allowed AppArmor profiles (default: ["runtime/default", "localhost/*"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-selinux-context` **Pods specify SELinux contexts**: Pods in SELinux-enabled clusters should specify SELinux contexts.
  * Collector(s): Parse securityContext for SELinux options
  * Component JSON:
    * `.k8s.workloads[].containers[].selinux_options` - SELinux context settings
    * `.k8s.workloads[].containers[].has_selinux` - Boolean for SELinux configuration
    * `.k8s.summary.all_have_selinux` - Boolean for all containers
  * Policy: Assert that SELinux options are specified where required
  * Configuration: Allowed SELinux levels, roles, types, and users
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-allowed-proc-mount` **Containers use allowed proc mount types**: Containers must use Default procMount type, not Unmasked.
  * Collector(s): Parse securityContext for procMount setting
  * Component JSON:
    * `.k8s.workloads[].containers[].proc_mount` - procMount type (Default or Unmasked)
    * `.k8s.workloads[].containers[].uses_unmasked_proc` - Boolean for Unmasked usage
    * `.k8s.summary.none_use_unmasked_proc` - Boolean for all containers
  * Policy: Assert that no containers use Unmasked procMount
  * Configuration: Allowed procMount types (default: ["Default"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Service Account Security (OPA/Gatekeeper Policies)

* `k8s-disable-sa-token-automount` **Pods disable automatic service account token mounting**: Pods should set automountServiceAccountToken to false unless explicitly needed.
  * Collector(s): Parse pod specifications for automountServiceAccountToken setting
  * Component JSON:
    * `.k8s.workloads[].automount_service_account_token` - Boolean for token auto-mount
    * `.k8s.summary.all_disable_sa_token_mount` - Boolean for all workloads
  * Policy: Assert that automountServiceAccountToken is false
  * Configuration: Exceptions for workloads that need Kubernetes API access
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-dedicated-service-account` **Pods use dedicated service accounts**: Pods should not use the default service account.
  * Collector(s): Parse pod specifications for serviceAccountName
  * Component JSON:
    * `.k8s.workloads[].service_account` - Service account name
    * `.k8s.workloads[].uses_default_sa` - Boolean for default SA usage
    * `.k8s.summary.none_use_default_sa` - Boolean for all workloads
  * Policy: Assert that pods use a dedicated service account, not "default"
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Resource Metadata (OPA/Gatekeeper Policies)

* `k8s-required-labels` **Resources have required labels**: All Kubernetes resources must have organization-required labels.
  * Collector(s): Parse resource metadata for label presence
  * Component JSON:
    * `.k8s.workloads[].labels` - Map of labels on the resource
    * `.k8s.workloads[].missing_required_labels` - Array of missing required labels
    * `.k8s.summary.all_have_required_labels` - Boolean for all resources
  * Policy: Assert that all required labels are present on resources
  * Configuration: Required label keys (e.g., ["app", "team", "environment", "version"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-required-annotations` **Resources have required annotations**: Resources must have organization-required annotations for operational metadata.
  * Collector(s): Parse resource metadata for annotation presence
  * Component JSON:
    * `.k8s.workloads[].annotations` - Map of annotations on the resource
    * `.k8s.workloads[].missing_required_annotations` - Array of missing required annotations
    * `.k8s.summary.all_have_required_annotations` - Boolean for all resources
  * Policy: Assert that all required annotations are present
  * Configuration: Required annotation keys (e.g., ["description", "owner", "oncall"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-label-naming-convention` **Label values follow naming conventions**: Label values must follow approved naming patterns.
  * Collector(s): Parse label values and validate against naming conventions
  * Component JSON:
    * `.k8s.workloads[].labels` - Map of labels
    * `.k8s.workloads[].invalid_label_values` - Array of labels with invalid values
  * Policy: Assert that label values match required patterns
  * Configuration: Regex patterns for label value validation
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Service Type Restrictions (OPA/Gatekeeper Policies)

* `k8s-no-nodeport` **Services do not use NodePort type**: NodePort services expose ports on all cluster nodes and should be avoided.
  * Collector(s): Parse Service resources for type field
  * Component JSON:
    * `.k8s.services[].type` - Service type (ClusterIP, NodePort, LoadBalancer)
    * `.k8s.services[].is_nodeport` - Boolean for NodePort type
    * `.k8s.summary.none_use_nodeport` - Boolean for all services
  * Policy: Assert that no services use NodePort type
  * Configuration: Exceptions for specific use cases
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-loadbalancer-annotations` **LoadBalancer services require annotations**: LoadBalancer services must have specific annotations for cloud provider configuration.
  * Collector(s): Parse LoadBalancer Service resources for required annotations
  * Component JSON:
    * `.k8s.services[].type` - Service type
    * `.k8s.services[].annotations` - Service annotations
    * `.k8s.services[].has_required_lb_annotations` - Boolean for required annotations
  * Policy: Assert that LoadBalancer services have required annotations
  * Configuration: Required LoadBalancer annotations (e.g., cloud provider specific settings)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-no-external-ips` **Services do not specify external IPs**: Services with externalIPs can be a security risk and should be restricted.
  * Collector(s): Parse Service resources for externalIPs field
  * Component JSON:
    * `.k8s.services[].external_ips` - Array of external IPs specified
    * `.k8s.services[].has_external_ips` - Boolean for externalIPs presence
    * `.k8s.summary.none_have_external_ips` - Boolean for all services
  * Policy: Assert that no services specify externalIPs (or only approved IPs)
  * Configuration: Approved external IP ranges if exceptions needed
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Replica and Scaling Limits (OPA/Gatekeeper Policies)

* `k8s-max-replica-count` **Deployments do not exceed maximum replica count**: Replicas should not exceed cluster capacity planning limits.
  * Collector(s): Parse Deployment and HPA specifications for replica counts
  * Component JSON:
    * `.k8s.workloads[].replicas` - Configured replica count
    * `.k8s.hpas[].max_replicas` - HPA maximum replicas
    * `.k8s.workloads[].exceeds_max_replicas` - Boolean for exceeding limit
  * Policy: Assert that replica count does not exceed configured maximum
  * Configuration: Maximum replica count (default: 100)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-hpa-scaling-range` **HPA scaling range is reasonable**: HPA min/max replica spread should be within reasonable bounds.
  * Collector(s): Parse HPA specifications for min and max replicas
  * Component JSON:
    * `.k8s.hpas[].min_replicas` - HPA minimum replicas
    * `.k8s.hpas[].max_replicas` - HPA maximum replicas
    * `.k8s.hpas[].replica_spread` - Difference between max and min
  * Policy: Assert that HPA replica spread is within acceptable range
  * Configuration: Maximum replica spread (default: 50)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Container Runtime Policies (OPA/Gatekeeper Policies)

* `k8s-image-pull-policy` **Containers specify image pull policy**: Containers should explicitly set imagePullPolicy for predictable behavior.
  * Collector(s): Parse container specifications for imagePullPolicy
  * Component JSON:
    * `.k8s.workloads[].containers[].image_pull_policy` - Configured pull policy
    * `.k8s.workloads[].containers[].has_pull_policy` - Boolean for explicit policy
  * Policy: Assert that imagePullPolicy is explicitly set
  * Configuration: Required pull policy values (e.g., ["Always", "IfNotPresent"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-image-digest` **Container images use SHA256 digests**: Container images should be referenced by digest for immutability.
  * Collector(s): Parse container image references for digest format
  * Component JSON:
    * `.k8s.workloads[].containers[].image` - Full image reference
    * `.k8s.workloads[].containers[].uses_digest` - Boolean for digest usage
    * `.k8s.summary.all_use_image_digests` - Boolean for all containers
  * Policy: Assert that all container images use SHA256 digests
  * Configuration: Whether to require digests or allow semver tags
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Container Image Policies

### Image Registry and Tagging

* `k8s-approved-registries` **Container images use approved registries**: All container images must be pulled from organization-approved registries.
  * Collector(s): Parse Kubernetes manifests and Dockerfiles for image references, extract registry hostnames
  * Component JSON:
    * `.k8s.workloads[].containers[].image` - Full image reference
    * `.k8s.workloads[].containers[].image_registry` - Extracted registry hostname
    * `.containers.registries_used` - List of all registries referenced
  * Policy: Assert that all image registries are in the approved list
  * Configuration: Approved registry list (e.g., ["gcr.io/company-name", "registry.internal.company.com"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-no-latest-tag` **Container images do not use latest tag**: Images must use explicit version tags, not "latest" which leads to unpredictable deployments.
  * Collector(s): Parse image references and extract tags
  * Component JSON:
    * `.k8s.workloads[].containers[].image_tag` - Extracted image tag
    * `.k8s.workloads[].containers[].uses_latest_tag` - Boolean indicating :latest usage
    * `.containers.summary.uses_latest_tag` - Boolean for any latest tag usage
  * Policy: Assert that no images use the latest tag
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-immutable-image-tags` **Container images use immutable tags**: Images should use content-addressable tags (SHA digests) or semantic version tags, not mutable tags.
  * Collector(s): Parse image references and detect tag patterns
  * Component JSON:
    * `.k8s.workloads[].containers[].image_tag` - Image tag
    * `.k8s.workloads[].containers[].uses_sha_digest` - Boolean for SHA digest usage
    * `.k8s.workloads[].containers[].tag_is_semver` - Boolean for semantic version
  * Policy: Assert that images use SHA digests or semantic version tags
  * Configuration: Acceptable tag patterns
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `dockerfile-pinned-versions` **Container images are pinned to specific versions**: Base images in Dockerfiles should be pinned to specific versions, not floating tags.
  * Collector(s): Parse Dockerfiles for FROM statements and validate version pinning
  * Component JSON:
    * `.containers.definitions[].base_images[].is_pinned` - Boolean indicating version is pinned
    * `.containers.definitions[].base_images[].tag` - Tag used for base image
  * Policy: Assert that all base images are version-pinned
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `dockerfile-approved-base-images` **Container images use approved base images**: Dockerfiles must use organization-approved base images.
  * Collector(s): Parse Dockerfiles for FROM statements and extract base image names
  * Component JSON:
    * `.containers.definitions[].base_images[].reference` - Full base image reference
    * `.containers.definitions[].base_images[].registry` - Base image registry
    * `.containers.definitions[].base_images[].is_approved` - Boolean for approved image
  * Policy: Assert that all base images are from the approved list
  * Configuration: Approved base image list
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Image Security

* `container-images-signed` **Container images are signed**: Deployed images must be cryptographically signed for supply chain security.
  * Collector(s): Check image signatures via container registry API or signing verification tool (Cosign, Notary)
  * Component JSON:
    * `.containers.builds[].signed` - Boolean indicating image is signed
    * `.containers.builds[].signature_verified` - Boolean indicating signature verification passed
    * `.containers.summary.all_signed` - Boolean for all deployed images
  * Policy: Assert that all deployed images are signed and verified
  * Configuration: Signing key references for verification
  * Strategy: Strategy 13 (Container Registry Policies)

* `container-provenance-attestation` **Container images have provenance attestations**: Images should have SLSA provenance attestations for build verification.
  * Collector(s): Query container registry for attestation metadata
  * Component JSON:
    * `.containers.builds[].has_provenance` - Boolean for provenance attestation
    * `.containers.builds[].slsa_level` - SLSA level achieved
  * Policy: Assert that images have provenance attestations
  * Configuration: Minimum SLSA level required
  * Strategy: Strategy 13 (Container Registry Policies)

* `container-required-labels` **Container images have required labels**: Built images must include standard labels for traceability (source repo, git SHA, build time).
  * Collector(s): Inspect container image metadata for OCI labels
  * Component JSON:
    * `.containers.builds[].labels` - Map of image labels
    * `.containers.builds[].has_git_sha_label` - Boolean for git SHA label
    * `.containers.builds[].has_source_label` - Boolean for source URL label
  * Policy: Assert that required labels are present on built images
  * Configuration: Required label keys (e.g., ["org.opencontainers.image.source", "org.opencontainers.image.revision"])
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 4 (CI Command Modification)

* `dockerfile-healthcheck` **Dockerfiles define HEALTHCHECK**: Dockerfiles should define a HEALTHCHECK instruction for container health monitoring.
  * Collector(s): Parse Dockerfiles for HEALTHCHECK instruction
  * Component JSON:
    * `.containers.definitions[].final_stage.has_healthcheck` - Boolean for healthcheck presence
    * `.containers.definitions[].healthcheck` - Healthcheck configuration
  * Policy: Assert that Dockerfiles include HEALTHCHECK instructions
  * Configuration: Whether this is required or optional
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `dockerfile-multi-stage` **Dockerfiles use multi-stage builds**: Dockerfiles should use multi-stage builds to minimize final image size and attack surface.
  * Collector(s): Parse Dockerfiles and count build stages
  * Component JSON:
    * `.containers.definitions[].stage_count` - Number of build stages
    * `.containers.definitions[].is_multi_stage` - Boolean for multi-stage usage
  * Policy: Assert that production Dockerfiles use multi-stage builds
  * Configuration: Tags requiring multi-stage builds
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Infrastructure as Code (Terraform/IaC)

### Configuration Validity

* `iac-terraform-valid` **Terraform files are syntactically valid**: All Terraform configuration files must parse without errors.
  * Collector(s): Run terraform validate or parse HCL files to detect syntax errors
  * Component JSON:
    * `.iac.files[].path` - Path to Terraform file
    * `.iac.files[].valid` - Boolean indicating valid syntax
    * `.iac.files[].errors` - Array of validation errors
    * `.iac.summary.all_valid` - Boolean for all files valid
  * Policy: Assert that all Terraform files are valid
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-provider-versions-pinned` **Terraform provider versions are pinned**: Providers must specify version constraints to ensure reproducible deployments.
  * Collector(s): Parse Terraform required_providers blocks for version constraints
  * Component JSON:
    * `.iac.providers[].name` - Provider name
    * `.iac.providers[].version_constraint` - Version constraint string
    * `.iac.providers[].is_pinned` - Boolean indicating version is pinned
    * `.iac.analysis.versions_pinned` - Boolean for all versions pinned
  * Policy: Assert that all providers have version constraints
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-module-versions-pinned` **Terraform module versions are pinned**: Module sources must specify version constraints or use commit SHAs.
  * Collector(s): Parse module blocks for source and version specifications
  * Component JSON:
    * `.iac.modules[].source` - Module source URL
    * `.iac.modules[].version` - Module version constraint
    * `.iac.modules[].is_pinned` - Boolean for pinned version
  * Policy: Assert that all modules have pinned versions
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-remote-backend` **Terraform uses remote backend**: Terraform must use a remote backend (S3, GCS, Terraform Cloud) for state management.
  * Collector(s): Parse Terraform backend configuration
  * Component JSON:
    * `.iac.backend.type` - Backend type (s3, gcs, remote, etc.)
    * `.iac.backend.configured` - Boolean for backend configuration
    * `.iac.analysis.has_backend` - Boolean indicating remote backend
  * Policy: Assert that a remote backend is configured
  * Configuration: Approved backend types
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-state-encrypted` **Terraform state is encrypted**: Remote backend must use encryption for state storage.
  * Collector(s): Parse backend configuration for encryption settings
  * Component JSON:
    * `.iac.backend.encrypted` - Boolean for encryption enabled
    * `.iac.backend.encryption_key` - KMS key reference if applicable
  * Policy: Assert that backend encryption is enabled
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Data Protection

* `iac-datastore-deletion-protection` **Datastores have deletion protection enabled**: Databases, storage buckets, and other datastores must have deletion protection.
  * Collector(s): Parse Terraform resources for deletion_protection or lifecycle prevent_destroy settings
  * Component JSON:
    * `.iac.datastores[].name` - Resource name
    * `.iac.datastores[].type` - Resource type (database, storage, cache)
    * `.iac.datastores[].deletion_protected` - Boolean for delete protection
    * `.iac.datastores.all_deletion_protected` - Boolean for all datastores
  * Policy: Assert that all datastores have deletion protection enabled
  * Configuration: Resource types considered datastores
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-datastore-encryption-at-rest` **Datastores have encryption at rest enabled**: All data storage resources must encrypt data at rest.
  * Collector(s): Parse Terraform resources for encryption configuration
  * Component JSON:
    * `.iac.datastores[].encrypted` - Boolean for encryption enabled
    * `.iac.datastores[].encryption_key` - KMS key reference if customer-managed
    * `.iac.datastores.all_encrypted` - Boolean for all datastores encrypted
  * Policy: Assert that all datastores have encryption at rest enabled
  * Configuration: Whether customer-managed keys are required
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-datastore-backup-enabled` **Datastores have backup enabled**: Critical datastores must have automated backups configured.
  * Collector(s): Parse Terraform resources for backup configuration
  * Component JSON:
    * `.iac.datastores[].backup_enabled` - Boolean for backup configuration
    * `.iac.datastores[].backup_retention_days` - Backup retention period
  * Policy: Assert that datastores have backup enabled with minimum retention
  * Configuration: Minimum backup retention days (default: 7)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-datastore-multi-az` **Datastores use Multi-AZ or regional replication**: Critical datastores should be deployed across availability zones.
  * Collector(s): Parse Terraform resources for multi-AZ configuration
  * Component JSON:
    * `.iac.datastores[].multi_az` - Boolean for multi-AZ deployment
    * `.iac.datastores[].replication_enabled` - Boolean for replication
  * Policy: Assert that critical datastores use multi-AZ deployment
  * Configuration: Tags requiring multi-AZ (e.g., ["tier1", "production"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Network Security

* `iac-internet-facing-waf` **Internet-facing services have WAF configured**: Publicly accessible HTTP services must have Web Application Firewall protection.
  * Collector(s): Parse Terraform for load balancers, API gateways, and associated WAF resources
  * Component JSON:
    * `.iac.resources[].internet_facing` - Boolean for public accessibility
    * `.iac.resources[].waf_enabled` - Boolean for WAF association
    * `.iac.analysis.has_waf` - Boolean for internet-facing resources with WAF
  * Policy: Assert that all internet-facing HTTP services have WAF configured
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-ddos-protection` **DDoS protection is enabled for public endpoints**: Public-facing infrastructure must have DDoS protection enabled.
  * Collector(s): Check for DDoS protection resources (AWS Shield, CloudFlare, etc.)
  * Component JSON:
    * `.iac.resources[].ddos_protection_enabled` - Boolean for DDoS protection
    * `.iac.analysis.has_ddos_protection` - Boolean for protected endpoints
  * Policy: Assert that DDoS protection is enabled for public endpoints
  * Configuration: Required protection level (standard vs advanced)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-lb-secure-ssl-policy` **Load balancers use secure SSL policies**: Load balancers must use TLS 1.2+ and strong cipher suites.
  * Collector(s): Parse load balancer Terraform resources for SSL/TLS policy configuration
  * Component JSON:
    * `.iac.resources[].ssl_policy` - SSL policy name or configuration
    * `.iac.resources[].min_tls_version` - Minimum TLS version
  * Policy: Assert that load balancers use approved SSL policies
  * Configuration: Approved SSL policy names, minimum TLS version (default: 1.2)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-no-unrestricted-ingress` **Security groups do not allow unrestricted ingress**: Security groups must not have 0.0.0.0/0 ingress rules except for specific ports.
  * Collector(s): Parse security group rules in Terraform
  * Component JSON:
    * `.iac.security_groups[].rules` - Array of security group rules
    * `.iac.security_groups[].has_unrestricted_ingress` - Boolean for 0.0.0.0/0 rules
    * `.iac.security_groups[].unrestricted_ports` - List of ports with unrestricted access
  * Policy: Assert that no unrestricted ingress rules exist except for allowed ports
  * Configuration: Allowed ports for public access (e.g., [80, 443])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-vpc-flow-logs` **VPC flow logs are enabled**: VPCs must have flow logging enabled for network monitoring.
  * Collector(s): Parse VPC and flow log Terraform resources
  * Component JSON:
    * `.iac.vpcs[].flow_logs_enabled` - Boolean for flow log configuration
    * `.iac.vpcs[].flow_log_destination` - Flow log destination (S3, CloudWatch)
  * Policy: Assert that VPCs have flow logs enabled
  * Configuration: Required flow log traffic type (all, accept, reject)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Resource Tagging

* `iac-required-tags` **All resources have required tags**: Infrastructure resources must have organization-required tags for cost allocation and ownership.
  * Collector(s): Parse Terraform resources for tag assignments
  * Component JSON:
    * `.iac.resources[].tags` - Map of resource tags
    * `.iac.resources[].missing_required_tags` - Array of missing required tags
    * `.iac.summary.all_properly_tagged` - Boolean for complete tagging
  * Policy: Assert that all resources have required tags
  * Configuration: Required tag keys (e.g., ["owner", "environment", "cost-center", "application"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-environment-tag-valid` **Environment tag matches deployment environment**: The environment tag must accurately reflect the deployment environment.
  * Collector(s): Extract environment tags and validate against known environments
  * Component JSON:
    * `.iac.resources[].tags.environment` - Environment tag value
    * `.iac.environment` - Expected environment from context
  * Policy: Assert that environment tags use approved values
  * Configuration: Approved environment values (e.g., ["development", "staging", "production"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### AWS-Specific Policies (OPA/Conftest Inspired)

* `iac-s3-block-public-access` **S3 buckets block public access**: S3 buckets must have public access blocked at the bucket level.
  * Collector(s): Parse Terraform aws_s3_bucket and aws_s3_bucket_public_access_block resources
  * Component JSON:
    * `.iac.s3_buckets[].name` - Bucket name
    * `.iac.s3_buckets[].block_public_acls` - Boolean for blocking public ACLs
    * `.iac.s3_buckets[].block_public_policy` - Boolean for blocking public policies
    * `.iac.s3_buckets[].ignore_public_acls` - Boolean for ignoring public ACLs
    * `.iac.s3_buckets[].restrict_public_buckets` - Boolean for restricting public access
    * `.iac.s3_buckets[].public_access_blocked` - Boolean for all four settings enabled
  * Policy: Assert that all S3 buckets have public access fully blocked
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-s3-versioning-enabled` **S3 buckets have versioning enabled**: S3 buckets should have versioning enabled for data protection.
  * Collector(s): Parse Terraform aws_s3_bucket_versioning resources
  * Component JSON:
    * `.iac.s3_buckets[].versioning_enabled` - Boolean for versioning status
  * Policy: Assert that S3 buckets have versioning enabled
  * Configuration: Exceptions for temporary/cache buckets
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-s3-encryption` **S3 buckets have server-side encryption**: S3 buckets must use server-side encryption for data at rest.
  * Collector(s): Parse Terraform aws_s3_bucket_server_side_encryption_configuration resources
  * Component JSON:
    * `.iac.s3_buckets[].encryption_enabled` - Boolean for SSE configuration
    * `.iac.s3_buckets[].encryption_algorithm` - Encryption algorithm (AES256, aws:kms)
    * `.iac.s3_buckets[].kms_key_id` - KMS key ID if using SSE-KMS
  * Policy: Assert that S3 buckets have encryption enabled
  * Configuration: Required encryption type (SSE-S3 or SSE-KMS)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-s3-access-logging` **S3 buckets have access logging enabled**: S3 buckets should log access requests for audit purposes.
  * Collector(s): Parse Terraform aws_s3_bucket_logging resources
  * Component JSON:
    * `.iac.s3_buckets[].logging_enabled` - Boolean for access logging
    * `.iac.s3_buckets[].logging_target_bucket` - Target bucket for logs
  * Policy: Assert that S3 buckets have access logging enabled
  * Configuration: Tags requiring logging (e.g., ["production", "sensitive"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-rds-encryption` **RDS instances have encryption enabled**: RDS database instances must encrypt storage at rest.
  * Collector(s): Parse Terraform aws_db_instance resources for storage_encrypted
  * Component JSON:
    * `.iac.rds_instances[].identifier` - RDS instance identifier
    * `.iac.rds_instances[].storage_encrypted` - Boolean for encryption status
    * `.iac.rds_instances[].kms_key_id` - KMS key ID if using CMK
  * Policy: Assert that RDS instances have storage encryption enabled
  * Configuration: Whether CMK is required vs AWS-managed key
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-rds-automated-backups` **RDS instances have automated backups**: RDS instances must have automated backups with appropriate retention.
  * Collector(s): Parse Terraform aws_db_instance resources for backup settings
  * Component JSON:
    * `.iac.rds_instances[].backup_retention_period` - Backup retention in days
    * `.iac.rds_instances[].backup_window` - Preferred backup window
  * Policy: Assert that backup retention period meets minimum requirement
  * Configuration: Minimum backup retention days (default: 7)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-rds-not-public` **RDS instances are not publicly accessible**: RDS instances should not be exposed to the public internet.
  * Collector(s): Parse Terraform aws_db_instance resources for publicly_accessible
  * Component JSON:
    * `.iac.rds_instances[].publicly_accessible` - Boolean for public access
  * Policy: Assert that RDS instances are not publicly accessible
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-rds-deletion-protection` **RDS instances have deletion protection**: Production RDS instances must have deletion protection enabled.
  * Collector(s): Parse Terraform aws_db_instance resources for deletion_protection
  * Component JSON:
    * `.iac.rds_instances[].deletion_protection` - Boolean for delete protection
  * Policy: Assert that production RDS instances have deletion protection
  * Configuration: Tags requiring deletion protection
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-ec2-imdsv2` **EC2 instances use IMDSv2**: EC2 instances must require Instance Metadata Service v2 (IMDSv2) to prevent SSRF attacks.
  * Collector(s): Parse Terraform aws_instance and aws_launch_template resources for metadata_options
  * Component JSON:
    * `.iac.ec2_instances[].http_tokens` - IMDS token requirement (optional or required)
    * `.iac.ec2_instances[].http_endpoint` - IMDS endpoint status
    * `.iac.ec2_instances[].uses_imdsv2` - Boolean for IMDSv2 enforcement
  * Policy: Assert that EC2 instances require IMDSv2 (http_tokens = "required")
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-ebs-encrypted` **EBS volumes are encrypted**: EBS volumes must be encrypted at rest.
  * Collector(s): Parse Terraform aws_ebs_volume and aws_instance resources for encryption
  * Component JSON:
    * `.iac.ebs_volumes[].encrypted` - Boolean for volume encryption
    * `.iac.ebs_volumes[].kms_key_id` - KMS key ID if using CMK
    * `.iac.summary.all_ebs_encrypted` - Boolean for all volumes
  * Policy: Assert that all EBS volumes are encrypted
  * Configuration: Whether CMK is required
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-ec2-no-public-ip` **EC2 instances do not have public IPs by default**: EC2 instances should not automatically receive public IP addresses.
  * Collector(s): Parse Terraform aws_instance resources for associate_public_ip_address
  * Component JSON:
    * `.iac.ec2_instances[].associate_public_ip` - Boolean for public IP assignment
    * `.iac.ec2_instances[].in_public_subnet` - Boolean for public subnet placement
  * Policy: Assert that EC2 instances do not auto-assign public IPs
  * Configuration: Exceptions for bastion hosts or public-facing instances
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-cloudtrail-enabled` **CloudTrail logging is enabled**: AWS accounts must have CloudTrail enabled for API auditing.
  * Collector(s): Parse Terraform aws_cloudtrail resources
  * Component JSON:
    * `.iac.cloudtrail.enabled` - Boolean for CloudTrail presence
    * `.iac.cloudtrail.multi_region` - Boolean for multi-region logging
    * `.iac.cloudtrail.log_file_validation` - Boolean for log integrity validation
    * `.iac.cloudtrail.s3_bucket` - Destination bucket for logs
  * Policy: Assert that CloudTrail is enabled with required settings
  * Configuration: Required CloudTrail settings (multi-region, validation, encryption)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-kms-key-rotation` **KMS keys have rotation enabled**: Customer-managed KMS keys must have automatic key rotation enabled.
  * Collector(s): Parse Terraform aws_kms_key resources for enable_key_rotation
  * Component JSON:
    * `.iac.kms_keys[].key_id` - KMS key ID
    * `.iac.kms_keys[].enable_key_rotation` - Boolean for rotation status
    * `.iac.kms_keys[].deletion_window` - Key deletion window in days
  * Policy: Assert that KMS keys have rotation enabled
  * Configuration: Minimum deletion window (default: 30 days)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-iam-no-wildcard-resource` **IAM policies do not use wildcard resources**: IAM policies should not grant access to all resources (*).
  * Collector(s): Parse Terraform aws_iam_policy documents for resource wildcards
  * Component JSON:
    * `.iac.iam_policies[].name` - Policy name
    * `.iac.iam_policies[].has_wildcard_resource` - Boolean for wildcard resources
    * `.iac.iam_policies[].wildcard_statements` - Statements with wildcards
  * Policy: Assert that IAM policies do not use wildcard resources
  * Configuration: Allowed wildcard patterns for specific use cases
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-iam-no-wildcard-action` **IAM policies do not use wildcard actions**: IAM policies should specify explicit actions, not wildcards.
  * Collector(s): Parse Terraform aws_iam_policy documents for action wildcards
  * Component JSON:
    * `.iac.iam_policies[].has_wildcard_action` - Boolean for wildcard actions
    * `.iac.iam_policies[].wildcard_action_statements` - Statements with action wildcards
  * Policy: Assert that IAM policies do not use wildcard actions
  * Configuration: Exceptions for admin policies if needed
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-sg-has-description` **Security groups have descriptions**: Security groups should have meaningful descriptions for documentation.
  * Collector(s): Parse Terraform aws_security_group resources for description field
  * Component JSON:
    * `.iac.security_groups[].name` - Security group name
    * `.iac.security_groups[].description` - Security group description
    * `.iac.security_groups[].has_description` - Boolean for non-empty description
  * Policy: Assert that security groups have non-empty descriptions
  * Configuration: Minimum description length
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-sg-rule-has-description` **Security group rules have descriptions**: Individual security group rules should have descriptions explaining their purpose.
  * Collector(s): Parse Terraform aws_security_group_rule resources for description
  * Component JSON:
    * `.iac.security_groups[].rules[].description` - Rule description
    * `.iac.security_groups[].rules[].has_description` - Boolean for description presence
  * Policy: Assert that security group rules have descriptions
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-lambda-no-public-url` **Lambda functions are not publicly accessible**: Lambda functions should not have public URL configurations without authentication.
  * Collector(s): Parse Terraform aws_lambda_function_url resources for authorization settings
  * Component JSON:
    * `.iac.lambda_functions[].function_name` - Function name
    * `.iac.lambda_functions[].has_public_url` - Boolean for public URL
    * `.iac.lambda_functions[].url_auth_type` - URL authorization type (NONE, AWS_IAM)
  * Policy: Assert that Lambda functions do not have unauthenticated public URLs
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Multi-Cloud Policies (OPA/Conftest Inspired)

* `iac-approved-instance-types` **Compute instances use approved machine types**: VMs and instances should use cost-effective and approved machine types.
  * Collector(s): Parse Terraform compute instance resources for instance types
  * Component JSON:
    * `.iac.compute_instances[].instance_type` - Instance/machine type
    * `.iac.compute_instances[].is_approved_type` - Boolean for approved type
  * Policy: Assert that instances use approved machine types
  * Configuration: Approved instance type patterns per environment
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-storage-lifecycle-policy` **Storage resources have lifecycle policies**: Object storage should have lifecycle policies for cost management.
  * Collector(s): Parse Terraform storage resources for lifecycle configurations
  * Component JSON:
    * `.iac.storage[].has_lifecycle_policy` - Boolean for lifecycle policy
    * `.iac.storage[].lifecycle_rules` - Array of lifecycle rules
  * Policy: Assert that storage resources have lifecycle policies
  * Configuration: Tags requiring lifecycle policies
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-approved-regions` **Resources are deployed in approved regions**: Infrastructure should only be deployed in organization-approved regions.
  * Collector(s): Parse Terraform provider and resource configurations for region settings
  * Component JSON:
    * `.iac.resources[].region` - Resource deployment region
    * `.iac.resources[].is_approved_region` - Boolean for approved region
    * `.iac.regions_used` - Array of all regions referenced
  * Policy: Assert that resources are deployed in approved regions only
  * Configuration: Approved region list (e.g., ["us-east-1", "us-west-2", "eu-west-1"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-database-private-endpoint` **Managed database services use private endpoints**: Database services should use private endpoints, not public access.
  * Collector(s): Parse Terraform database resources for network configuration
  * Component JSON:
    * `.iac.databases[].uses_private_endpoint` - Boolean for private endpoint
    * `.iac.databases[].uses_private_link` - Boolean for private link
    * `.iac.databases[].publicly_accessible` - Boolean for public access
  * Policy: Assert that databases use private endpoints
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-lb-access-logs` **Load balancers have access logs enabled**: Load balancers should log access requests for security monitoring.
  * Collector(s): Parse Terraform load balancer resources for access logging configuration
  * Component JSON:
    * `.iac.load_balancers[].access_logs_enabled` - Boolean for access logging
    * `.iac.load_balancers[].access_logs_bucket` - Log destination bucket
  * Policy: Assert that load balancers have access logging enabled
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-registry-vulnerability-scanning` **Container registries have vulnerability scanning**: Container registries should have automatic vulnerability scanning enabled.
  * Collector(s): Parse Terraform container registry resources for scan configuration
  * Component JSON:
    * `.iac.container_registries[].scan_on_push` - Boolean for scan on push
    * `.iac.container_registries[].scanning_enabled` - Boolean for scanning configuration
  * Policy: Assert that container registries have vulnerability scanning enabled
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-secrets-rotation` **Secrets Manager secrets have rotation configured**: Secrets stored in managed secret services should have rotation.
  * Collector(s): Parse Terraform secrets manager resources for rotation configuration
  * Component JSON:
    * `.iac.secrets[].rotation_enabled` - Boolean for rotation configuration
    * `.iac.secrets[].rotation_lambda` - Rotation Lambda ARN
    * `.iac.secrets[].rotation_days` - Rotation period in days
  * Policy: Assert that secrets have rotation configured
  * Configuration: Maximum rotation period (default: 90 days)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Deployment Configuration

### Deployment Strategies

* `deploy-rolling-update-strategy` **Deployments use rolling update strategy**: Kubernetes Deployments should use RollingUpdate strategy for zero-downtime deploys.
  * Collector(s): Parse Deployment manifests for strategy configuration
  * Component JSON:
    * `.k8s.workloads[].strategy.type` - Deployment strategy type
    * `.k8s.workloads[].strategy.max_surge` - Maximum surge during rollout
    * `.k8s.workloads[].strategy.max_unavailable` - Maximum unavailable during rollout
  * Policy: Assert that Deployments use RollingUpdate strategy
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `deploy-zero-unavailable` **Rolling update allows zero unavailable pods**: Rolling update should be configured to maintain full availability during deploys.
  * Collector(s): Parse RollingUpdate strategy configuration
  * Component JSON:
    * `.k8s.workloads[].strategy.max_unavailable` - Maximum unavailable pods
  * Policy: Assert that maxUnavailable is 0 or a small percentage
  * Configuration: Maximum unavailable threshold (default: 0 or 25%)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `deploy-canary-configured` **Canary deployment capability is configured**: Production services should support canary deployments for safe rollouts.
  * Collector(s): Check for canary deployment configuration (Argo Rollouts, Flagger, or similar)
  * Component JSON:
    * `.deployment.canary.configured` - Boolean for canary support
    * `.deployment.canary.tool` - Canary deployment tool used
    * `.deployment.canary.steps` - Array of canary rollout steps
  * Policy: Assert that canary deployment is configured for production services
  * Configuration: Tags requiring canary support
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `deploy-blue-green-configured` **Blue-green deployment capability exists**: Critical services should support blue-green deployments for instant rollback.
  * Collector(s): Check for blue-green deployment configuration
  * Component JSON:
    * `.deployment.blue_green.configured` - Boolean for blue-green support
    * `.deployment.blue_green.tool` - Deployment tool used
  * Policy: Assert that blue-green deployment is available for critical services
  * Configuration: Tags requiring blue-green support
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Deployment Gates and Approvals

* `deploy-production-approval` **Production deployments require manual approval**: Deployments to production must go through an approval gate.
  * Collector(s): Parse CD pipeline configuration (ArgoCD, Spinnaker, GitHub Actions) for approval requirements
  * Component JSON:
    * `.deployment.approval_required` - Boolean for approval requirement
    * `.deployment.approvers` - List of required approvers or teams
    * `.deployment.approval_policy` - Approval policy details
  * Policy: Assert that production deployments require approval
  * Configuration: Environments requiring approval (default: ["production"])
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `deploy-dry-run-validation` **Deployment dry-run validation is performed**: Deployments should run validation or dry-run before actual application.
  * Collector(s): Check CD pipeline for dry-run or validation steps
  * Component JSON:
    * `.deployment.dry_run.enabled` - Boolean for dry-run validation
    * `.deployment.dry_run.tool` - Tool used for validation (kubectl diff, terraform plan)
  * Policy: Assert that dry-run validation is part of the deployment process
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `deploy-auto-rollback` **Deployment includes automated rollback capability**: Deployment pipelines should support automated rollback on failure.
  * Collector(s): Check CD configuration for rollback settings
  * Component JSON:
    * `.deployment.auto_rollback.enabled` - Boolean for auto-rollback
    * `.deployment.auto_rollback.triggers` - Conditions triggering rollback
  * Policy: Assert that automated rollback is configured
  * Configuration: Required rollback triggers (e.g., ["failed-health-check", "error-rate-threshold"])
  * Strategy: Strategy 1 (CI Tool Execution Detection)

### GitOps and CD Configuration

* `deploy-argocd-app-exists` **ArgoCD Application exists for the component**: Components using GitOps must have an ArgoCD Application or ApplicationSet.
  * Collector(s): Check for ArgoCD application manifests or query ArgoCD API
  * Component JSON:
    * `.deployment.argocd.application_exists` - Boolean for ArgoCD app
    * `.deployment.argocd.application_name` - Application name
    * `.deployment.argocd.sync_policy` - Sync policy configuration
  * Policy: Assert that ArgoCD Application exists for GitOps-managed components
  * Configuration: Tags requiring ArgoCD (e.g., ["gitops", "kubernetes"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `deploy-argocd-sync-policy` **ArgoCD sync policy is appropriately configured**: ArgoCD Applications should have proper sync policies (prune, self-heal).
  * Collector(s): Parse ArgoCD Application manifests for sync policy
  * Component JSON:
    * `.deployment.argocd.sync_policy.automated` - Boolean for automated sync
    * `.deployment.argocd.sync_policy.prune` - Boolean for prune enabled
    * `.deployment.argocd.sync_policy.self_heal` - Boolean for self-heal
  * Policy: Assert that sync policy meets requirements
  * Configuration: Required sync policy settings
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `deploy-approved-runner` **CD pipeline runs in appropriate environment**: Deployment pipelines should execute from secure, controlled environments.
  * Collector(s): Extract CD execution environment from pipeline runs
  * Component JSON:
    * `.deployment.pipeline.runner_type` - Type of runner (self-hosted, cloud)
    * `.deployment.pipeline.runner_labels` - Runner labels or tags
  * Policy: Assert that deployment pipelines use approved runner environments
  * Configuration: Approved runner types or labels
  * Strategy: Strategy 1 (CI Tool Execution Detection)

---

## Deployment Lifecycle

### Deployment Freshness

* `deploy-recent-deployment` **Component has recent successful deployment**: Production components should have been deployed recently to avoid drift.
  * Collector(s): Query deployment system or Kubernetes API for last deployment timestamp
  * Component JSON:
    * `.runtime.last_deployment.timestamp` - ISO 8601 timestamp of last deployment
    * `.runtime.last_deployment.days_ago` - Days since last deployment
    * `.runtime.last_deployment.status` - Deployment status (success, failed)
  * Policy: Assert that last successful deployment is within threshold
  * Configuration: Maximum days since deployment (default: 30)
  * Strategy: Strategy 3 (Cross-Component and Historical Data Queries) or Strategy 15 (Runtime and Deployed State Verification)

* `deploy-not-stale` **No stale deployments in production**: Deployments older than threshold should be flagged for review.
  * Collector(s): Query Kubernetes or deployment system for deployment age
  * Component JSON:
    * `.runtime.deployment_age_days` - Age of current deployment in days
    * `.runtime.is_stale` - Boolean indicating stale deployment
  * Policy: Assert that deployment is not older than threshold
  * Configuration: Stale deployment threshold days (default: 90)
  * Strategy: Strategy 3 (Cross-Component and Historical Data Queries)

* `deploy-version-current` **Deployed version matches latest in default branch**: The deployed version should not be significantly behind the source.
  * Collector(s): Compare deployed git SHA or version with latest in repository
  * Component JSON:
    * `.runtime.deployed_version` - Git SHA or version of deployed code
    * `.runtime.latest_version` - Latest version in default branch
    * `.runtime.commits_behind` - Number of commits behind latest
  * Policy: Assert that deployed version is not too far behind source
  * Configuration: Maximum commits behind (default: 10)
  * Strategy: Strategy 15 (Runtime and Deployed State Verification)

### Multi-Environment Configuration

* `deploy-env-specific-config` **Environment-specific configuration is managed**: Different environments should have separate configuration management.
  * Collector(s): Check for environment-specific config files or ConfigMaps
  * Component JSON:
    * `.deployment.environments` - Array of configured environments
    * `.deployment.environments[].config_path` - Path to environment config
    * `.deployment.environments[].config_exists` - Boolean for config presence
  * Policy: Assert that required environments have configuration
  * Configuration: Required environments (e.g., ["development", "staging", "production"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `deploy-secrets-env-isolated` **Secrets are environment-specific**: Secrets must be separated by environment to prevent cross-environment exposure.
  * Collector(s): Check secret references in manifests for environment isolation
  * Component JSON:
    * `.deployment.secrets.environment_isolated` - Boolean for secret isolation
    * `.deployment.secrets.shared_secrets` - List of secrets shared across environments
  * Policy: Assert that secrets are environment-specific
  * Configuration: Allowed shared secret patterns
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `deploy-production-cluster-isolated` **Production and non-production use separate clusters**: Production workloads should run on dedicated clusters.
  * Collector(s): Extract cluster information from deployment configuration
  * Component JSON:
    * `.deployment.clusters[].name` - Cluster name
    * `.deployment.clusters[].environment` - Environment served by cluster
    * `.deployment.production_cluster_isolated` - Boolean for isolation
  * Policy: Assert that production uses dedicated clusters
  * Configuration: Production cluster identifiers
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Network and Service Mesh

### Kubernetes Networking

* `k8s-network-policy-exists` **Network policies exist for workloads**: Production workloads should have NetworkPolicies restricting traffic.
  * Collector(s): Parse Kubernetes manifests for NetworkPolicy resources
  * Component JSON:
    * `.k8s.network_policies[].name` - NetworkPolicy name
    * `.k8s.network_policies[].target_pods` - Pod selector for policy
    * `.k8s.summary.has_network_policies` - Boolean for policy existence
  * Policy: Assert that production workloads have associated NetworkPolicies
  * Configuration: Tags requiring network policies
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-default-deny-policy` **Default deny network policy exists**: Namespaces should have a default deny policy with explicit allow rules.
  * Collector(s): Parse NetworkPolicies for default deny patterns
  * Component JSON:
    * `.k8s.network_policies[].is_default_deny` - Boolean for default deny policy
    * `.k8s.namespace.has_default_deny` - Boolean for namespace-level default deny
  * Policy: Assert that default deny policy exists in production namespaces
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-egress-restricted` **Egress traffic is restricted**: Workloads should have egress NetworkPolicies limiting outbound traffic.
  * Collector(s): Parse NetworkPolicies for egress rules
  * Component JSON:
    * `.k8s.network_policies[].has_egress_rules` - Boolean for egress restrictions
    * `.k8s.summary.egress_restricted` - Boolean for workload egress restrictions
  * Policy: Assert that egress traffic is restricted for sensitive workloads
  * Configuration: Tags requiring egress restrictions
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Service Mesh

* `k8s-mesh-sidecar-injected` **Service mesh sidecar is injected**: Workloads in service mesh namespaces should have sidecar injection.
  * Collector(s): Check for service mesh sidecar containers or injection annotations
  * Component JSON:
    * `.k8s.workloads[].has_mesh_sidecar` - Boolean for sidecar presence
    * `.k8s.workloads[].mesh_sidecar_version` - Sidecar version
    * `.k8s.mesh.enabled` - Boolean for mesh participation
  * Policy: Assert that workloads in mesh namespaces have sidecars
  * Configuration: Namespaces requiring mesh
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-mesh-mtls-enabled` **mTLS is enabled between services**: Service mesh mTLS should be enabled for inter-service communication.
  * Collector(s): Check service mesh configuration for mTLS settings
  * Component JSON:
    * `.k8s.mesh.mtls_enabled` - Boolean for mTLS configuration
    * `.k8s.mesh.mtls_mode` - mTLS mode (strict, permissive)
  * Policy: Assert that mTLS is enabled in strict mode
  * Configuration: Required mTLS mode (default: strict)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Encryption and Security

### Encryption in Transit

* `k8s-ingress-tls` **Services use TLS for external communication**: All external-facing services must use TLS encryption.
  * Collector(s): Check Ingress and Service configurations for TLS settings
  * Component JSON:
    * `.k8s.ingresses[].tls_configured` - Boolean for TLS configuration
    * `.k8s.ingresses[].tls_secret` - TLS secret reference
    * `.k8s.summary.all_ingress_tls` - Boolean for all ingresses using TLS
  * Policy: Assert that all Ingresses have TLS configured
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-certs-auto-managed` **TLS certificates are managed properly**: TLS certificates should be managed by cert-manager or similar automation.
  * Collector(s): Check for cert-manager Certificate resources or annotations
  * Component JSON:
    * `.k8s.certificates[].managed_by` - Certificate management tool
    * `.k8s.certificates[].auto_renewal` - Boolean for auto-renewal
    * `.k8s.summary.certs_auto_managed` - Boolean for automated management
  * Policy: Assert that TLS certificates are automatically managed
  * Configuration: Approved certificate managers
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Secrets Management

* `k8s-no-plain-text-secrets` **Secrets are not stored in plain text in manifests**: Kubernetes Secrets should not be committed as plain YAML.
  * Collector(s): Scan Kubernetes manifests for Secret resources with plain data
  * Component JSON:
    * `.k8s.secrets[].source` - How secret is managed (sealed, external, vault)
    * `.k8s.secrets[].is_plain_text` - Boolean for plain text secrets
    * `.k8s.summary.no_plain_secrets` - Boolean for no plain secrets
  * Policy: Assert that no plain text secrets exist in manifests
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-external-secrets-manager` **External secrets manager is used**: Secrets should be managed by an external secrets manager (Vault, AWS Secrets Manager).
  * Collector(s): Check for ExternalSecret resources or Vault annotations
  * Component JSON:
    * `.k8s.secrets[].external_source` - External secret manager type
    * `.k8s.summary.uses_external_secrets` - Boolean for external secrets usage
  * Policy: Assert that secrets use external secrets manager
  * Configuration: Approved secret managers (e.g., ["vault", "aws-secrets-manager", "external-secrets"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-secrets-rotation-policy` **Secrets have appropriate rotation policy**: Secrets should be configured for regular rotation.
  * Collector(s): Check secret management configuration for rotation settings
  * Component JSON:
    * `.secrets.rotation_enabled` - Boolean for rotation configuration
    * `.secrets.rotation_period_days` - Rotation period in days
  * Policy: Assert that secret rotation is configured
  * Configuration: Maximum rotation period (default: 90 days)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Helm Chart Standards

### Chart Validation

* `helm-lint-passed` **Helm charts pass linting**: Helm charts must pass helm lint validation.
  * Collector(s): Run helm lint on chart directories
  * Component JSON:
    * `.helm.charts[].path` - Chart directory path
    * `.helm.charts[].lint_passed` - Boolean for lint success
    * `.helm.charts[].lint_errors` - Array of lint errors
  * Policy: Assert that all Helm charts pass linting
  * Configuration: Lint strictness level
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `helm-version-semver` **Helm chart version follows semantic versioning**: Chart versions must follow semver for proper version management.
  * Collector(s): Parse Chart.yaml for version field
  * Component JSON:
    * `.helm.charts[].version` - Chart version
    * `.helm.charts[].version_is_semver` - Boolean for semver compliance
  * Policy: Assert that chart versions follow semantic versioning
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `helm-values-schema` **Helm chart has values schema**: Charts should include a values.schema.json for validation.
  * Collector(s): Check for values.schema.json in chart directory
  * Component JSON:
    * `.helm.charts[].has_values_schema` - Boolean for schema presence
    * `.helm.charts[].schema_path` - Path to schema file
  * Policy: Assert that production charts have values schema
  * Configuration: Tags requiring values schema
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `helm-dependencies-pinned` **Helm dependencies are version-pinned**: Chart dependencies must specify version constraints.
  * Collector(s): Parse Chart.yaml dependencies for version specifications
  * Component JSON:
    * `.helm.charts[].dependencies[].name` - Dependency name
    * `.helm.charts[].dependencies[].version` - Version constraint
    * `.helm.charts[].dependencies[].is_pinned` - Boolean for version pinning
  * Policy: Assert that all dependencies have pinned versions
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Database Configuration and Schema Standards

### Schema Naming Conventions

* `db-table-naming-convention` **Table names follow naming convention**: Database tables must follow organization naming standards (e.g., snake_case, plural).
  * Collector(s): Parse SQL migration files or connect to database to extract table names
  * Component JSON:
    * `.database.schema.tables[].name` - Table name
    * `.database.schema.tables[].follows_convention` - Boolean for naming compliance
    * `.database.schema.tables[].convention_violations` - Array of specific violations
    * `.database.schema.naming_compliant` - Boolean for all tables
  * Policy: Assert that all table names follow the configured naming convention
  * Configuration: Naming pattern regex (e.g., "^[a-z][a-z0-9]*(_[a-z0-9]+)*$"), plural vs singular preference
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-column-naming-convention` **Column names follow naming convention**: Database columns must follow organization naming standards (e.g., snake_case).
  * Collector(s): Parse SQL migration files or introspect database schema for column names
  * Component JSON:
    * `.database.schema.tables[].columns[].name` - Column name
    * `.database.schema.tables[].columns[].follows_convention` - Boolean for naming compliance
    * `.database.schema.column_naming_compliant` - Boolean for all columns
  * Policy: Assert that all column names follow the configured naming convention
  * Configuration: Naming pattern regex, reserved word blacklist
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-pk-naming-convention` **Primary key columns follow convention**: Primary key columns should use consistent naming (e.g., "id" or "table_id").
  * Collector(s): Parse schema for primary key column names
  * Component JSON:
    * `.database.schema.tables[].primary_key.columns` - Array of PK column names
    * `.database.schema.tables[].primary_key.follows_convention` - Boolean for PK naming
  * Policy: Assert that primary key columns follow naming convention
  * Configuration: Allowed PK column names (default: ["id"]), UUID vs integer preference
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-fk-naming-convention` **Foreign key columns follow naming convention**: Foreign key columns should be named consistently (e.g., "referenced_table_id").
  * Collector(s): Parse schema for foreign key column names and their referenced tables
  * Component JSON:
    * `.database.schema.tables[].foreign_keys[].column` - FK column name
    * `.database.schema.tables[].foreign_keys[].references_table` - Referenced table name
    * `.database.schema.tables[].foreign_keys[].follows_convention` - Boolean for FK naming
  * Policy: Assert that FK columns follow pattern like "referenced_table_id"
  * Configuration: FK naming pattern (default: "{table}_id")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-index-naming-convention` **Index names follow naming convention**: Index names should include table name, column(s), and index type.
  * Collector(s): Parse schema for index definitions and names
  * Component JSON:
    * `.database.schema.tables[].indexes[].name` - Index name
    * `.database.schema.tables[].indexes[].columns` - Columns in the index
    * `.database.schema.tables[].indexes[].type` - Index type (btree, hash, unique, etc.)
    * `.database.schema.tables[].indexes[].follows_convention` - Boolean for naming
  * Policy: Assert that index names follow convention (e.g., "idx_table_column")
  * Configuration: Index naming pattern (e.g., "idx_{table}_{columns}", "ix_{table}_{columns}")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-constraint-naming-convention` **Constraint names follow naming convention**: Constraints should have meaningful names, not auto-generated ones.
  * Collector(s): Parse schema for constraint names (unique, check, FK constraints)
  * Component JSON:
    * `.database.schema.tables[].constraints[].name` - Constraint name
    * `.database.schema.tables[].constraints[].type` - Constraint type (unique, check, fk)
    * `.database.schema.tables[].constraints[].is_auto_generated` - Boolean for system-generated name
  * Policy: Assert that constraints have explicit meaningful names
  * Configuration: Constraint naming patterns per type
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-enum-naming-convention` **Enum types follow naming convention**: Custom enum types should follow naming conventions.
  * Collector(s): Parse schema for enum type definitions
  * Component JSON:
    * `.database.schema.enums[].name` - Enum type name
    * `.database.schema.enums[].values` - Array of enum values
    * `.database.schema.enums[].follows_convention` - Boolean for naming
  * Policy: Assert that enum names follow convention (e.g., snake_case with suffix)
  * Configuration: Enum naming pattern, value naming pattern
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Required Schema Elements

* `db-tables-have-pk` **Tables have primary keys**: Every table must have a primary key defined.
  * Collector(s): Parse schema to verify primary key presence on all tables
  * Component JSON:
    * `.database.schema.tables[].has_primary_key` - Boolean for PK presence
    * `.database.schema.tables[].primary_key` - PK definition if present
    * `.database.schema.all_have_primary_keys` - Boolean for all tables
  * Policy: Assert that all tables have primary keys
  * Configuration: Exceptions for specific table patterns (e.g., join tables)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-tables-have-timestamps` **Tables have timestamp columns**: Tables should include created_at and updated_at columns for auditing.
  * Collector(s): Parse schema for standard timestamp columns
  * Component JSON:
    * `.database.schema.tables[].has_created_at` - Boolean for created_at presence
    * `.database.schema.tables[].has_updated_at` - Boolean for updated_at presence
    * `.database.schema.tables[].has_required_timestamps` - Boolean for both
  * Policy: Assert that tables include required timestamp columns
  * Configuration: Required timestamp columns (default: ["created_at", "updated_at"]), exceptions
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-soft-delete-pattern` **Tables use soft delete pattern**: Tables should use soft delete (deleted_at column) instead of hard delete.
  * Collector(s): Parse schema for soft delete column presence
  * Component JSON:
    * `.database.schema.tables[].has_deleted_at` - Boolean for deleted_at/soft delete column
    * `.database.schema.tables[].uses_soft_delete` - Boolean for soft delete pattern
  * Policy: Assert that tables tagged for soft delete have the pattern implemented
  * Configuration: Tags requiring soft delete, soft delete column name (default: "deleted_at")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-fk-indexed` **Foreign keys have indexes**: Columns used in foreign key relationships should have indexes for query performance.
  * Collector(s): Parse schema for FK columns and verify corresponding indexes exist
  * Component JSON:
    * `.database.schema.tables[].foreign_keys[].column` - FK column
    * `.database.schema.tables[].foreign_keys[].has_index` - Boolean for index on FK
    * `.database.schema.all_fk_indexed` - Boolean for all FKs indexed
  * Policy: Assert that all foreign key columns have indexes
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-adequate-indexes` **Tables have appropriate indexes for common queries**: Tables should have indexes on frequently queried columns.
  * Collector(s): Parse schema for index coverage, optionally analyze query patterns
  * Component JSON:
    * `.database.schema.tables[].indexes` - Array of index definitions
    * `.database.schema.tables[].suggested_indexes` - Array of suggested missing indexes
    * `.database.schema.tables[].has_adequate_indexes` - Boolean for index coverage
  * Policy: Assert that tables have indexes on commonly queried columns
  * Configuration: Column patterns that should be indexed (e.g., "*_id", "status", "type")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-uuid-native-type` **UUID columns use appropriate type**: UUID columns should use native UUID type, not VARCHAR.
  * Collector(s): Parse schema for columns that appear to store UUIDs
  * Component JSON:
    * `.database.schema.tables[].columns[].appears_uuid` - Boolean for UUID-like column
    * `.database.schema.tables[].columns[].type` - Actual column type
    * `.database.schema.tables[].columns[].uses_native_uuid` - Boolean for native UUID type
  * Policy: Assert that UUID columns use native UUID/GUID type
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Schema Security

* `db-no-plaintext-passwords` **No plaintext password columns**: Schema should not have columns that appear to store plaintext passwords.
  * Collector(s): Parse schema for column names suggesting password storage
  * Component JSON:
    * `.database.schema.tables[].columns[].is_password_column` - Boolean for password-like name
    * `.database.schema.tables[].columns[].appears_hashed` - Boolean for hash-like type/name
    * `.database.schema.has_plaintext_password_risk` - Boolean for potential issues
  * Policy: Assert that no columns suggest plaintext password storage
  * Configuration: Password column name patterns to detect
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-sensitive-columns-tagged` **Sensitive columns are identified**: Columns containing PII or sensitive data should be tagged/documented.
  * Collector(s): Parse schema and column comments for sensitive data markers
  * Component JSON:
    * `.database.schema.tables[].columns[].is_sensitive` - Boolean for sensitive column
    * `.database.schema.tables[].columns[].sensitivity_level` - Classification level
    * `.database.schema.tables[].columns[].has_sensitivity_tag` - Boolean for documented sensitivity
  * Policy: Assert that columns matching sensitive patterns are tagged
  * Configuration: Sensitive column name patterns (e.g., "*_ssn", "*_email", "*_phone")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-pii-columns-protected` **PII columns have appropriate handling**: Columns containing PII should have encryption or masking configured.
  * Collector(s): Parse schema and related encryption/masking configurations
  * Component JSON:
    * `.database.schema.tables[].columns[].contains_pii` - Boolean for PII column
    * `.database.schema.tables[].columns[].encryption_configured` - Boolean for encryption
    * `.database.schema.tables[].columns[].masking_configured` - Boolean for data masking
  * Policy: Assert that PII columns have appropriate protection configured
  * Configuration: PII protection requirements per data type
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-audit-tables-exist` **Audit log tables exist for sensitive operations**: Sensitive tables should have corresponding audit log tables.
  * Collector(s): Parse schema for audit log table patterns
  * Component JSON:
    * `.database.schema.tables[].requires_audit` - Boolean for audit requirement
    * `.database.schema.tables[].has_audit_table` - Boolean for audit table existence
    * `.database.schema.audit_tables` - Array of audit table names
  * Policy: Assert that tables requiring audit have corresponding audit tables
  * Configuration: Tags requiring audit, audit table naming pattern
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Migration Standards

* `db-migration-naming-convention` **Migration files follow naming convention**: Migration files should have consistent naming with timestamps and descriptions.
  * Collector(s): Scan migration directory for file names and validate format
  * Component JSON:
    * `.database.migrations[].filename` - Migration file name
    * `.database.migrations[].follows_convention` - Boolean for naming compliance
    * `.database.migrations[].timestamp` - Extracted timestamp
    * `.database.migrations[].description` - Extracted description
  * Policy: Assert that migration files follow naming convention
  * Configuration: Migration naming pattern (e.g., "{timestamp}_{description}.sql", "V{version}__{description}.sql")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-migration-reversible` **Migrations are reversible**: Migration files should include rollback/down migrations.
  * Collector(s): Parse migration files for up/down sections or corresponding rollback files
  * Component JSON:
    * `.database.migrations[].has_rollback` - Boolean for rollback presence
    * `.database.migrations[].rollback_file` - Path to rollback file if separate
    * `.database.migrations[].is_reversible` - Boolean for reversibility assessment
  * Policy: Assert that migrations have corresponding rollback definitions
  * Configuration: Whether rollbacks are required for all or just production
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-migration-destructive-approved` **Migrations avoid destructive changes without approval**: DROP TABLE, DROP COLUMN, and similar should require explicit approval.
  * Collector(s): Parse migration SQL for destructive DDL statements
  * Component JSON:
    * `.database.migrations[].contains_destructive_ddl` - Boolean for destructive operations
    * `.database.migrations[].destructive_statements` - Array of destructive statements found
    * `.database.migrations[].has_approval_marker` - Boolean for approval annotation
  * Policy: Assert that destructive migrations have approval markers or are blocked
  * Configuration: Destructive DDL patterns, approval annotation format
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-migration-no-mixed-ddl-dml` **Migrations do not modify data in DDL files**: Schema migrations should not mix DDL and DML statements.
  * Collector(s): Parse migration files for DML statements (INSERT, UPDATE, DELETE)
  * Component JSON:
    * `.database.migrations[].contains_dml` - Boolean for DML presence
    * `.database.migrations[].dml_statements` - Array of DML statements found
    * `.database.migrations[].type` - Migration type (ddl, dml, mixed)
  * Policy: Assert that DDL migrations do not contain DML statements
  * Configuration: Whether to allow mixed migrations, DML-only migration patterns
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-migration-online-ddl` **Large table migrations use online DDL**: Migrations on large tables should use non-blocking techniques.
  * Collector(s): Parse migration SQL and correlate with table size information
  * Component JSON:
    * `.database.migrations[].affected_tables` - Tables modified by migration
    * `.database.migrations[].uses_online_ddl` - Boolean for online DDL usage
    * `.database.migrations[].has_lock_risk` - Boolean for potential table lock
  * Policy: Assert that migrations on large tables use online DDL patterns
  * Configuration: Table size threshold for online DDL requirement, online DDL patterns
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-migration-idempotent` **Migration files are idempotent where possible**: Migrations should use IF EXISTS/IF NOT EXISTS for safety.
  * Collector(s): Parse migration SQL for idempotent patterns
  * Component JSON:
    * `.database.migrations[].is_idempotent` - Boolean for idempotent patterns
    * `.database.migrations[].uses_if_exists` - Boolean for IF EXISTS usage
    * `.database.migrations[].uses_if_not_exists` - Boolean for IF NOT EXISTS usage
  * Policy: Assert that migrations use idempotent patterns where applicable
  * Configuration: Statements requiring idempotent patterns
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Database Performance Standards

* `db-column-limit` **Tables do not exceed column limit**: Tables should not have too many columns, suggesting normalization issues.
  * Collector(s): Parse schema and count columns per table
  * Component JSON:
    * `.database.schema.tables[].column_count` - Number of columns
    * `.database.schema.tables[].exceeds_column_limit` - Boolean for exceeding limit
  * Policy: Assert that tables do not exceed maximum column count
  * Configuration: Maximum columns per table (default: 50)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-varchar-length` **VARCHAR columns have appropriate lengths**: VARCHAR columns should have explicit, reasonable length limits.
  * Collector(s): Parse schema for VARCHAR column definitions
  * Component JSON:
    * `.database.schema.tables[].columns[].type` - Column type
    * `.database.schema.tables[].columns[].length` - Defined length for VARCHAR
    * `.database.schema.tables[].columns[].length_appropriate` - Boolean for reasonable length
  * Policy: Assert that VARCHAR columns have explicit lengths and are not excessively large
  * Configuration: Maximum VARCHAR length (default: 1000), patterns requiring specific lengths
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-lob-columns-justified` **TEXT/BLOB columns are justified**: Large object columns should only be used when necessary.
  * Collector(s): Parse schema for TEXT, BLOB, CLOB, BYTEA columns
  * Component JSON:
    * `.database.schema.tables[].columns[].is_lob_type` - Boolean for LOB type
    * `.database.schema.tables[].lob_column_count` - Count of LOB columns
  * Policy: Assert that LOB columns are explicitly approved or limited
  * Configuration: Maximum LOB columns per table, approved LOB column patterns
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-index-column-limit` **Indexes do not have too many columns**: Composite indexes should not include too many columns.
  * Collector(s): Parse schema for index column counts
  * Component JSON:
    * `.database.schema.tables[].indexes[].column_count` - Number of columns in index
    * `.database.schema.tables[].indexes[].exceeds_column_limit` - Boolean for too many columns
  * Policy: Assert that indexes do not have excessive columns
  * Configuration: Maximum index columns (default: 5)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-no-duplicate-indexes` **No duplicate indexes exist**: Schema should not have redundant/duplicate indexes.
  * Collector(s): Parse schema and detect indexes with identical or subset column lists
  * Component JSON:
    * `.database.schema.tables[].duplicate_indexes` - Array of duplicate index pairs
    * `.database.schema.tables[].has_duplicate_indexes` - Boolean for duplicates present
  * Policy: Assert that no duplicate or redundant indexes exist
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-appropriate-data-types` **Appropriate data types are used**: Columns should use appropriate types (not storing everything as VARCHAR).
  * Collector(s): Parse schema and analyze column types vs naming patterns
  * Component JSON:
    * `.database.schema.tables[].columns[].type_appropriate` - Boolean for appropriate type
    * `.database.schema.tables[].columns[].suggested_type` - Suggested better type if any
  * Policy: Assert that columns use appropriate data types
  * Configuration: Type suggestions per column pattern (e.g., "*_at" should be TIMESTAMP)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Database Documentation

* `db-tables-have-comments` **Tables have comments/descriptions**: All tables should have descriptive comments explaining their purpose.
  * Collector(s): Parse schema for table comments/descriptions
  * Component JSON:
    * `.database.schema.tables[].comment` - Table comment/description
    * `.database.schema.tables[].has_comment` - Boolean for comment presence
    * `.database.schema.all_tables_documented` - Boolean for all tables
  * Policy: Assert that all tables have non-empty comments
  * Configuration: Minimum comment length, exceptions for specific tables
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-columns-have-comments` **Columns have comments/descriptions**: Important columns should have comments explaining their purpose and valid values.
  * Collector(s): Parse schema for column comments/descriptions
  * Component JSON:
    * `.database.schema.tables[].columns[].comment` - Column comment
    * `.database.schema.tables[].columns[].has_comment` - Boolean for comment presence
    * `.database.schema.column_documentation_percentage` - Percentage of documented columns
  * Policy: Assert that column documentation meets minimum percentage
  * Configuration: Minimum documentation percentage (default: 80%)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-enums-documented` **Enum values are documented**: Enum types should have documentation for each value.
  * Collector(s): Parse schema and documentation for enum value explanations
  * Component JSON:
    * `.database.schema.enums[].values` - Enum values
    * `.database.schema.enums[].documented_values` - Values with documentation
    * `.database.schema.enums[].fully_documented` - Boolean for all values documented
  * Policy: Assert that enum values are documented
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-schema-diagram-current` **Schema diagram is up to date**: Database should have an ERD or schema diagram that reflects current state.
  * Collector(s): Check for schema diagram files and compare timestamps with migrations
  * Component JSON:
    * `.database.documentation.schema_diagram_exists` - Boolean for diagram presence
    * `.database.documentation.schema_diagram_path` - Path to diagram file
    * `.database.documentation.diagram_last_updated` - Last update timestamp
    * `.database.documentation.diagram_up_to_date` - Boolean for current diagram
  * Policy: Assert that schema diagram exists and was updated recently
  * Configuration: Maximum days since diagram update (default: 30)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Database Operational Standards

* `db-connection-pooling` **Connection pooling is configured**: Applications should use connection pooling for database access.
  * Collector(s): Parse application configuration for database connection pool settings
  * Component JSON:
    * `.database.connection.pool_enabled` - Boolean for connection pooling
    * `.database.connection.pool_size` - Pool size configuration
    * `.database.connection.max_connections` - Maximum connections
  * Policy: Assert that connection pooling is configured
  * Configuration: Minimum/maximum pool size
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-query-timeout` **Query timeout is configured**: Database queries should have timeout limits to prevent runaway queries.
  * Collector(s): Parse database and application configuration for timeout settings
  * Component JSON:
    * `.database.connection.query_timeout` - Query timeout value
    * `.database.connection.statement_timeout` - Statement timeout value
    * `.database.connection.has_timeout` - Boolean for timeout configuration
  * Policy: Assert that query timeout is configured
  * Configuration: Maximum timeout value (default: 30 seconds)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-read-replicas-used` **Read replicas are used for read operations**: Applications should route read queries to read replicas where available.
  * Collector(s): Parse application and infrastructure configuration for read replica usage
  * Component JSON:
    * `.database.replicas.read_replicas_exist` - Boolean for read replica presence
    * `.database.replicas.read_replica_usage_configured` - Boolean for app configuration
    * `.database.replicas.replica_count` - Number of read replicas
  * Policy: Assert that applications are configured to use read replicas
  * Configuration: Tags requiring read replica usage
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-backup-verification` **Database backup verification is documented**: Backup restoration should be periodically tested and documented.
  * Collector(s): Check for backup verification documentation and timestamps
  * Component JSON:
    * `.database.backup.verification_documented` - Boolean for documentation
    * `.database.backup.last_verification_date` - Last verification timestamp
    * `.database.backup.days_since_verification` - Days since last verification
  * Policy: Assert that backup verification was performed within threshold
  * Configuration: Maximum days between verifications (default: 90)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-pitr-enabled` **Database has point-in-time recovery**: Production databases should support point-in-time recovery.
  * Collector(s): Check database/IaC configuration for PITR settings
  * Component JSON:
    * `.database.backup.pitr_enabled` - Boolean for PITR configuration
    * `.database.backup.retention_period` - PITR retention period
  * Policy: Assert that PITR is enabled for production databases
  * Configuration: Minimum retention period (default: 7 days)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-slow-query-logging` **Slow query logging is enabled**: Database should log slow queries for performance analysis.
  * Collector(s): Check database configuration for slow query log settings
  * Component JSON:
    * `.database.logging.slow_query_log_enabled` - Boolean for slow query logging
    * `.database.logging.slow_query_threshold` - Threshold for slow query (ms)
  * Policy: Assert that slow query logging is enabled
  * Configuration: Maximum slow query threshold (default: 1000ms)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `db-metrics-collected` **Database metrics are collected**: Database should have metrics collection configured for monitoring.
  * Collector(s): Check for database metrics/monitoring configuration
  * Component JSON:
    * `.database.monitoring.metrics_enabled` - Boolean for metrics collection
    * `.database.monitoring.metrics_endpoint` - Metrics endpoint or exporter
    * `.database.monitoring.key_metrics_collected` - Array of collected metrics
  * Policy: Assert that database metrics collection is configured
  * Configuration: Required metrics (e.g., ["connections", "queries", "replication_lag"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Summary Policies

* `k8s-manifests-valid` **Kubernetes manifests are all valid**: All Kubernetes manifest files must be syntactically valid.
  * Collector(s): Parse all YAML files with Kubernetes manifest patterns
  * Component JSON:
    * `.k8s.manifests[].valid` - Boolean for manifest validity
    * `.k8s.manifests[].error` - Error message if invalid
    * `.k8s.summary.all_valid` - Boolean for all manifests valid
  * Policy: Assert that all Kubernetes manifests are valid
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `k8s-security-contexts-compliant` **All security contexts are properly configured**: Aggregate check that all container security settings are correct.
  * Collector(s): Aggregate security context checks from all containers
  * Component JSON:
    * `.k8s.summary.all_non_root` - All run as non-root
    * `.k8s.summary.all_read_only_root_fs` - All have read-only root FS
    * `.k8s.summary.none_privileged` - None are privileged
    * `.k8s.summary.security_compliant` - Aggregate security compliance
  * Policy: Assert that aggregate security compliance is true
  * Configuration: Which security checks to include in aggregate
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `iac-compliance-score` **Infrastructure meets compliance requirements**: Aggregate check that IaC meets organizational compliance standards.
  * Collector(s): Aggregate IaC compliance checks
  * Component JSON:
    * `.iac.datastores.all_deletion_protected` - All datastores protected
    * `.iac.datastores.all_encrypted` - All datastores encrypted
    * `.iac.analysis.has_waf` - WAF configured where needed
    * `.iac.summary.compliance_score` - Numeric compliance score
  * Policy: Assert that compliance score meets threshold
  * Configuration: Minimum compliance score (default: 100%)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)
