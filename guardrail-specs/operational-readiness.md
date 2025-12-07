# Operational Readiness Guardrails

This document specifies possible policies for the **Operational Readiness** category. These guardrails cover documentation and runbooks, on-call and incident management, observability (logging, metrics, tracing), health checks, alerting, disaster recovery, capacity planning, and anomaly detection.

---

## Documentation & Knowledge Base

### Runbooks

* **Runbook exists for the service**: Every production service must have a runbook documenting operational procedures, troubleshooting steps, and escalation paths.
  * Collector(s): Check for runbook file in standard locations (docs/runbook.md, runbook/), or verify runbook URL in catalog annotations or README
  * Component JSON:
    * `.oncall.runbook.exists` - Boolean indicating runbook presence
    * `.oncall.runbook.path` - Path to runbook file if in repository
    * `.oncall.runbook.url` - URL to external runbook if hosted elsewhere
    * `.oncall.runbook.source` - Where runbook was discovered (file, catalog, readme)
  * Policy: Assert that a runbook exists either in the repository or is linked from the service catalog
  * Configuration: Expected runbook locations, acceptable external wiki patterns

* **Runbook contains required sections**: Runbooks must include standard sections covering common operational scenarios.
  * Collector(s): Parse runbook file (Markdown) and extract section headings for comparison against required sections
  * Component JSON:
    * `.oncall.runbook.sections` - Array of section headings found in runbook
    * `.oncall.runbook.has_required_sections` - Boolean for all required sections present
    * `.oncall.runbook.missing_sections` - Array of missing required sections
  * Policy: Assert that all required sections are present in the runbook
  * Configuration: Required section names (default: ["Overview", "Architecture", "Dependencies", "Common Issues", "Troubleshooting", "Escalation", "Recovery Procedures"])

* **Runbook was updated recently**: Runbooks must be kept up-to-date to remain useful during incidents.
  * Collector(s): Check file modification timestamp for runbook, or query wiki API for last update time
  * Component JSON:
    * `.oncall.runbook.last_updated` - ISO 8601 timestamp of last runbook update
    * `.oncall.runbook.days_since_update` - Days since last update
    * `.oncall.runbook.is_stale` - Boolean indicating runbook is stale
  * Policy: Assert that runbook was updated within the configured threshold
  * Configuration: Maximum days since update (default: 90)

* **Runbook is linked from service catalog**: The runbook URL should be registered in the service catalog for discoverability during incidents.
  * Collector(s): Parse service catalog entry (Backstage catalog-info.yaml) for runbook annotation
  * Component JSON:
    * `.catalog.annotations.runbook` - Runbook URL from catalog annotation
    * `.catalog.annotations.runbook_exists` - Boolean for runbook annotation presence
  * Policy: Assert that runbook annotation is present in service catalog
  * Configuration: Expected annotation key (default: "runbook" or "docs/runbook")

### SLA/SLO Documentation

* **SLA is defined for the service**: Production services must have documented Service Level Agreements defining availability and performance commitments.
  * Collector(s): Check for SLA definition in catalog annotations, dedicated SLA file, or README section
  * Component JSON:
    * `.oncall.sla.defined` - Boolean indicating SLA is defined
    * `.oncall.sla.uptime_percentage` - Documented uptime commitment (e.g., 99.9)
    * `.oncall.sla.response_time_ms` - Documented response time SLA in milliseconds
    * `.oncall.sla.source` - Where SLA was discovered (catalog, file, readme)
  * Policy: Assert that SLA is defined for production services
  * Configuration: Tags requiring SLA (default: ["production", "tier1", "tier2"])

* **SLOs are defined with error budgets**: Services should have Service Level Objectives with measurable targets and error budgets.
  * Collector(s): Check for SLO definitions in catalog, dedicated SLO files, or monitoring configuration (Prometheus SLO rules, Datadog SLO monitors)
  * Component JSON:
    * `.oncall.slo.defined` - Boolean indicating SLOs are defined
    * `.oncall.slo.objectives` - Array of SLO definitions with targets
    * `.oncall.slo.has_error_budget` - Boolean for error budget definition
    * `.oncall.slo.error_budget_percentage` - Error budget percentage
  * Policy: Assert that SLOs are defined with error budgets for production services
  * Configuration: Required SLO types (default: ["availability", "latency"])

* **SLO dashboard exists**: SLO progress and error budget consumption should be visualized in a dashboard.
  * Collector(s): Check catalog annotations for SLO dashboard link, or query monitoring system API for SLO dashboard existence
  * Component JSON:
    * `.oncall.slo.dashboard_exists` - Boolean for SLO dashboard presence
    * `.oncall.slo.dashboard_url` - URL to SLO dashboard
  * Policy: Assert that SLO dashboard exists and is linked
  * Configuration: None

### Architecture Documentation

* **Architecture diagram exists**: Services must have architecture diagrams showing component relationships and data flows.
  * Collector(s): Check for architecture diagram files (PNG, SVG, draw.io, Mermaid) in docs/ folder or linked from README
  * Component JSON:
    * `.repo.documentation.architecture_diagram_exists` - Boolean for diagram presence
    * `.repo.documentation.architecture_diagram_path` - Path to diagram file
    * `.repo.documentation.architecture_diagram_format` - Diagram format (image, mermaid, drawio)
  * Policy: Assert that architecture diagram exists
  * Configuration: Accepted diagram file patterns, accepted formats

* **Dependency documentation is current**: Service dependencies (upstream and downstream) must be documented and kept current.
  * Collector(s): Parse catalog-info.yaml for dependency declarations, or extract from architecture documentation
  * Component JSON:
    * `.catalog.dependencies` - Array of declared service dependencies
    * `.catalog.apis.consumes` - APIs consumed by the service
    * `.catalog.apis.provides` - APIs provided by the service
    * `.catalog.dependencies_documented` - Boolean for dependency documentation presence
  * Policy: Assert that service dependencies are documented in the catalog
  * Configuration: None

---

## On-Call & Incident Management

### On-Call Schedule

* **On-call schedule is configured**: Production services must have an on-call schedule configured in the incident management system (PagerDuty, OpsGenie, VictorOps).
  * Collector(s): Query PagerDuty/OpsGenie API using service ID from catalog annotations to verify schedule exists
  * Component JSON:
    * `.oncall.schedule.exists` - Boolean indicating schedule is configured
    * `.oncall.schedule.id` - Schedule ID in incident management system
    * `.oncall.schedule.name` - Schedule name
    * `.oncall.source.tool` - Incident management tool (pagerduty, opsgenie, victorops)
  * Policy: Assert that on-call schedule is configured for production services
  * Configuration: Tags requiring on-call (default: ["production"])

* **On-call schedule has minimum participants**: On-call rotations must have a minimum number of participants to avoid burnout and ensure coverage.
  * Collector(s): Query incident management API to get schedule participant count
  * Component JSON:
    * `.oncall.schedule.participants` - Number of people in the rotation
    * `.oncall.schedule.participant_list` - Array of participant identifiers
    * `.oncall.summary.min_participants` - Minimum participant count found
  * Policy: Assert that on-call rotation has at least the minimum required participants
  * Configuration: Minimum participants (default: 4)

* **On-call schedule covers 24/7**: Production services must have continuous on-call coverage without gaps.
  * Collector(s): Query incident management API to analyze schedule coverage
  * Component JSON:
    * `.oncall.schedule.coverage_percentage` - Percentage of time covered by schedule
    * `.oncall.schedule.has_gaps` - Boolean indicating coverage gaps exist
    * `.oncall.schedule.gap_hours` - Total hours of gaps in coverage
  * Policy: Assert that schedule provides 100% coverage (24/7)
  * Configuration: Minimum coverage percentage (default: 100)

* **On-call rotation length is appropriate**: Rotation shifts should not be too long to prevent fatigue, nor too short to prevent disruption.
  * Collector(s): Query incident management API to get rotation configuration
  * Component JSON:
    * `.oncall.schedule.rotation` - Rotation type (daily, weekly, custom)
    * `.oncall.schedule.shift_length_hours` - Length of each shift in hours
    * `.oncall.schedule.rotation_length_days` - Length of rotation cycle in days
  * Policy: Assert that shift and rotation lengths are within acceptable bounds
  * Configuration: Min/max shift length (default: 12-168 hours), min/max rotation length (default: 7-14 days)

* **On-call schedule has backup/secondary coverage**: Critical services should have secondary on-call coverage for escalation.
  * Collector(s): Query incident management API to check for secondary/backup schedule
  * Component JSON:
    * `.oncall.schedule.has_secondary` - Boolean for secondary schedule existence
    * `.oncall.schedule.secondary_id` - Secondary schedule ID
    * `.oncall.schedule.secondary_participants` - Participants in secondary rotation
  * Policy: Assert that secondary on-call coverage exists for critical services
  * Configuration: Tags requiring secondary coverage (default: ["tier1", "critical"])

### Escalation Policies

* **Escalation policy is configured**: Services must have an escalation policy defining how incidents escalate when unacknowledged.
  * Collector(s): Query incident management API for escalation policy associated with the service
  * Component JSON:
    * `.oncall.escalation.exists` - Boolean for escalation policy presence
    * `.oncall.escalation.id` - Escalation policy ID
    * `.oncall.escalation.name` - Escalation policy name
  * Policy: Assert that escalation policy is configured for production services
  * Configuration: None

* **Escalation policy has multiple levels**: Escalation policies must have multiple levels to ensure incidents are handled even if primary responders are unavailable.
  * Collector(s): Query incident management API to get escalation policy details
  * Component JSON:
    * `.oncall.escalation.levels` - Number of escalation levels
    * `.oncall.escalation.level_details` - Array of escalation level configurations
    * `.oncall.escalation.final_level_is_management` - Boolean for management in final level
  * Policy: Assert that escalation policy has at least the minimum required levels
  * Configuration: Minimum escalation levels (default: 3)

* **Escalation timeouts are appropriate**: Escalation timeouts should be short enough to ensure timely response but not so short as to cause alert fatigue.
  * Collector(s): Query incident management API for escalation timeout configuration
  * Component JSON:
    * `.oncall.escalation.timeout_minutes` - Timeout before escalation at each level
    * `.oncall.escalation.total_escalation_time` - Total time before reaching final level
  * Policy: Assert that escalation timeouts are within acceptable ranges
  * Configuration: Min/max timeout per level (default: 5-30 minutes), max total escalation time (default: 60 minutes)

* **Escalation policy includes management for critical incidents**: Critical incident escalation paths should include management notification.
  * Collector(s): Query incident management API and verify management targets in escalation levels
  * Component JSON:
    * `.oncall.escalation.includes_management` - Boolean for management in escalation chain
    * `.oncall.escalation.management_level` - Level at which management is engaged
  * Policy: Assert that management is included in escalation for critical services
  * Configuration: Tags requiring management escalation (default: ["tier1", "critical"])

### Team & HRIS Integration

* **On-call participants are active employees**: On-call schedule participants should be validated against HRIS/HR system to ensure they are current employees.
  * Collector(s): Query incident management API for participants, then cross-reference with HRIS API (Workday, BambooHR, etc.)
  * Component JSON:
    * `.oncall.schedule.participant_list` - Array of participant identifiers
    * `.oncall.schedule.inactive_participants` - Array of participants not found in HRIS
    * `.oncall.schedule.all_participants_active` - Boolean for all participants validated
  * Policy: Assert that all on-call participants are active employees
  * Configuration: HRIS system to validate against

* **On-call team matches service ownership**: The on-call team should align with the team that owns the service in the catalog.
  * Collector(s): Compare service owner from catalog with on-call schedule team assignment
  * Component JSON:
    * `.catalog.entity.owner` - Service owner from catalog
    * `.oncall.schedule.team` - Team associated with on-call schedule
    * `.oncall.ownership_aligned` - Boolean for ownership alignment
  * Policy: Assert that on-call team aligns with service ownership
  * Configuration: None

* **Catalog team correlates with HRIS**: Service ownership teams in the catalog should exist in the HRIS/HR system.
  * Collector(s): Query HRIS API to validate team names/IDs from catalog
  * Component JSON:
    * `.catalog.entity.owner` - Team owner from catalog
    * `.catalog.owner_exists_in_hris` - Boolean for team validation
    * `.catalog.hris_team_id` - Corresponding HRIS team ID
  * Policy: Assert that catalog team exists in HRIS
  * Configuration: HRIS integration details

### Incident Management Integration

* **Service is registered in incident management system**: The service must be registered in PagerDuty/OpsGenie with proper routing.
  * Collector(s): Query incident management API to verify service exists with the expected identifier
  * Component JSON:
    * `.oncall.service.exists` - Boolean for service registration
    * `.oncall.service.id` - Service ID in incident management system
    * `.oncall.service.integration_key` - Integration key for alerting
  * Policy: Assert that service is registered in incident management system
  * Configuration: Expected service naming pattern

* **Incident management service is linked from catalog**: The incident management service ID should be documented in the service catalog for quick access.
  * Collector(s): Parse catalog annotations for PagerDuty/OpsGenie service reference
  * Component JSON:
    * `.catalog.annotations.pagerduty_service` - PagerDuty service ID from catalog
    * `.catalog.annotations.opsgenie_team` - OpsGenie team from catalog
    * `.catalog.annotations.incident_service_linked` - Boolean for any incident service annotation
  * Policy: Assert that incident management service is linked in catalog
  * Configuration: Expected annotation keys

* **Service has incident communication channel**: Services should have a designated communication channel (Slack, Teams) for incident coordination.
  * Collector(s): Parse catalog annotations for Slack channel reference
  * Component JSON:
    * `.catalog.annotations.slack_channel` - Slack channel from catalog
    * `.catalog.annotations.teams_channel` - Microsoft Teams channel from catalog
    * `.catalog.annotations.has_incident_channel` - Boolean for incident channel presence
  * Policy: Assert that incident communication channel is documented
  * Configuration: Expected annotation keys

---

## Observability - Logging

### Logging Configuration

* **Structured logging is configured**: Applications must use structured logging (JSON format) for machine-parseable log output.
  * Collector(s): Analyze application configuration files for logging framework settings, or parse log output samples from CI
  * Component JSON:
    * `.observability.logging.configured` - Boolean for logging configuration presence
    * `.observability.logging.structured` - Boolean for structured logging format
    * `.observability.logging.format` - Log format (json, text, logfmt)
    * `.observability.logging.framework` - Logging framework used
  * Policy: Assert that structured logging is configured
  * Configuration: Acceptable log formats (default: ["json", "logfmt"])

* **Logging uses approved library**: Applications should use organization-approved logging libraries for consistency.
  * Collector(s): Parse dependency files for logging library dependencies, or check configuration for logging framework
  * Component JSON:
    * `.observability.logging.framework` - Logging framework/library used
    * `.observability.logging.is_approved_library` - Boolean for approved library usage
  * Policy: Assert that logging uses an approved library
  * Configuration: Approved logging libraries per language (e.g., Go: ["zap", "zerolog"], Python: ["structlog", "python-json-logger"])

* **Log levels are appropriately configured**: Production logging should use appropriate log levels (not DEBUG in production).
  * Collector(s): Parse application configuration for log level settings
  * Component JSON:
    * `.observability.logging.level` - Configured log level
    * `.observability.logging.level_configurable` - Boolean for runtime configurability
  * Policy: Assert that log level is not too verbose for production (not DEBUG)
  * Configuration: Minimum log level for production (default: INFO)

* **Logs include correlation IDs**: Logs must include request/trace correlation IDs for distributed tracing integration.
  * Collector(s): Analyze logging configuration or sample logs for correlation ID fields
  * Component JSON:
    * `.observability.logging.has_correlation_id` - Boolean for correlation ID presence
    * `.observability.logging.correlation_id_field` - Field name for correlation ID
  * Policy: Assert that logs include correlation/trace IDs
  * Configuration: Expected correlation ID field names (default: ["trace_id", "request_id", "correlation_id"])

* **Logs include required context fields**: Logs should include standard context fields for consistent querying and analysis.
  * Collector(s): Analyze logging configuration for included context fields
  * Component JSON:
    * `.observability.logging.context_fields` - Array of configured context fields
    * `.observability.logging.has_required_fields` - Boolean for all required fields present
    * `.observability.logging.missing_fields` - Array of missing required fields
  * Policy: Assert that logs include all required context fields
  * Configuration: Required context fields (default: ["service", "environment", "version", "timestamp", "level"])

* **Sensitive data is excluded from logs**: Logs must not contain PII, credentials, or other sensitive information.
  * Collector(s): Analyze logging configuration for field filtering/masking, or scan log samples for sensitive patterns
  * Component JSON:
    * `.observability.logging.sensitive_field_masking` - Boolean for sensitive field masking configured
    * `.observability.logging.masked_fields` - Array of fields configured for masking
    * `.observability.logging.has_sensitive_data_risk` - Boolean for potential sensitive data in logs
  * Policy: Assert that sensitive data masking is configured
  * Configuration: Fields that should be masked (default: ["password", "token", "secret", "authorization", "credit_card"])

### Log Aggregation

* **Logs are shipped to centralized system**: Application logs must be shipped to a centralized log aggregation system (ELK, Splunk, Datadog, CloudWatch).
  * Collector(s): Check for log shipping configuration in application or infrastructure (Fluentd, Filebeat, Vector configs)
  * Component JSON:
    * `.observability.logging.aggregation_configured` - Boolean for log aggregation setup
    * `.observability.logging.aggregation_destination` - Destination system (elasticsearch, splunk, datadog)
    * `.observability.logging.log_shipper` - Log shipper used (fluentd, filebeat, vector)
  * Policy: Assert that log aggregation is configured
  * Configuration: Required aggregation destination

* **Log retention meets compliance requirements**: Log retention periods must meet organizational and compliance requirements.
  * Collector(s): Query log aggregation system API for retention settings, or check IaC for log retention configuration
  * Component JSON:
    * `.observability.logging.retention_days` - Configured log retention in days
    * `.observability.logging.meets_retention_requirement` - Boolean for compliance
  * Policy: Assert that log retention meets minimum requirements
  * Configuration: Minimum retention days (default: 90), per-tag overrides for compliance

---

## Observability - Metrics

### Metrics Configuration

* **Application exposes metrics endpoint**: Applications must expose a metrics endpoint for scraping by monitoring systems.
  * Collector(s): Check application configuration for metrics endpoint, or probe the metrics endpoint in CI/CD
  * Component JSON:
    * `.observability.metrics.configured` - Boolean for metrics configuration
    * `.observability.metrics.endpoint` - Metrics endpoint path (e.g., /metrics)
    * `.observability.metrics.format` - Metrics format (prometheus, statsd, otlp)
  * Policy: Assert that metrics endpoint is configured
  * Configuration: Expected endpoint paths, accepted formats

* **Metrics endpoint is declared in Kubernetes**: Kubernetes workloads should have metrics annotations/labels for service discovery.
  * Collector(s): Parse Kubernetes manifests for Prometheus scrape annotations or ServiceMonitor resources
  * Component JSON:
    * `.k8s.workloads[].has_metrics_annotations` - Boolean for metrics annotations
    * `.k8s.workloads[].metrics_port` - Port exposed for metrics
    * `.k8s.workloads[].metrics_path` - Path for metrics endpoint
    * `.k8s.has_service_monitor` - Boolean for ServiceMonitor resource
  * Policy: Assert that metrics scraping is configured in Kubernetes
  * Configuration: Whether annotations or ServiceMonitor is required

* **Golden signals are monitored**: Services must monitor the four golden signals (latency, traffic, errors, saturation).
  * Collector(s): Query monitoring system for metrics matching golden signal patterns, or analyze metrics configuration
  * Component JSON:
    * `.observability.metrics.golden_signals.latency` - Boolean for latency metrics
    * `.observability.metrics.golden_signals.traffic` - Boolean for traffic/request metrics
    * `.observability.metrics.golden_signals.errors` - Boolean for error rate metrics
    * `.observability.metrics.golden_signals.saturation` - Boolean for resource saturation metrics
    * `.observability.summary.golden_signals_complete` - Boolean for all four signals monitored
  * Policy: Assert that all four golden signals are monitored
  * Configuration: None

* **Request latency histogram is tracked**: Services must track request latency using histograms for percentile calculations.
  * Collector(s): Query monitoring system or analyze metrics configuration for histogram metrics
  * Component JSON:
    * `.observability.metrics.has_latency_histogram` - Boolean for histogram presence
    * `.observability.metrics.latency_histogram_name` - Name of latency histogram metric
    * `.observability.metrics.latency_buckets` - Configured histogram buckets
  * Policy: Assert that request latency histogram is configured
  * Configuration: Required histogram bucket ranges

* **Error rate metrics are tracked**: Services must track error rates for reliability monitoring.
  * Collector(s): Query monitoring system or analyze metrics configuration for error metrics
  * Component JSON:
    * `.observability.metrics.has_error_rate` - Boolean for error rate metrics
    * `.observability.metrics.error_metric_name` - Name of error rate metric
  * Policy: Assert that error rate metrics are tracked
  * Configuration: None

* **Resource utilization metrics are exposed**: Services should expose resource utilization metrics (CPU, memory, connections).
  * Collector(s): Query monitoring system for resource metrics, or check for standard runtime metrics
  * Component JSON:
    * `.observability.metrics.has_resource_metrics` - Boolean for resource metrics
    * `.observability.metrics.resource_metrics` - Array of resource metric names
  * Policy: Assert that resource utilization metrics are exposed
  * Configuration: Required resource metrics (default: ["cpu", "memory", "connections"])

* **Business metrics are tracked**: Services should track business-relevant metrics beyond technical health.
  * Collector(s): Query monitoring system for custom business metrics, or analyze metrics configuration
  * Component JSON:
    * `.observability.metrics.has_business_metrics` - Boolean for business metrics
    * `.observability.metrics.business_metrics` - Array of business metric names
  * Policy: Assert that business metrics are defined for production services
  * Configuration: Tags requiring business metrics, minimum business metric count

### Dashboards

* **Service dashboard exists**: Every production service must have an operational dashboard for monitoring.
  * Collector(s): Check catalog annotations for dashboard link, or query monitoring system API (Grafana, Datadog) for dashboard existence
  * Component JSON:
    * `.observability.dashboard.exists` - Boolean for dashboard presence
    * `.observability.dashboard.url` - Dashboard URL
    * `.observability.dashboard.source` - Dashboard system (grafana, datadog, newrelic)
  * Policy: Assert that service dashboard exists
  * Configuration: Dashboard system to check, expected dashboard naming pattern

* **Dashboard is linked from service catalog**: The dashboard URL should be registered in the service catalog for easy access.
  * Collector(s): Parse catalog annotations for dashboard link
  * Component JSON:
    * `.catalog.annotations.grafana_dashboard` - Grafana dashboard URL from catalog
    * `.catalog.annotations.datadog_dashboard` - Datadog dashboard URL from catalog
    * `.catalog.annotations.dashboard_linked` - Boolean for any dashboard annotation
  * Policy: Assert that dashboard is linked in service catalog
  * Configuration: Expected annotation keys

* **Dashboard includes golden signals**: Service dashboards should visualize all four golden signals.
  * Collector(s): Query dashboard API to analyze dashboard panels and metrics
  * Component JSON:
    * `.observability.dashboard.panels` - Array of dashboard panel definitions
    * `.observability.dashboard.has_golden_signals` - Boolean for golden signal coverage
    * `.observability.dashboard.missing_signals` - Array of missing golden signals
  * Policy: Assert that dashboard includes all golden signals
  * Configuration: None

* **Dashboard includes SLO progress**: Dashboards should show SLO status and error budget consumption.
  * Collector(s): Query dashboard API to check for SLO-related panels
  * Component JSON:
    * `.observability.dashboard.has_slo_panels` - Boolean for SLO panels
    * `.observability.dashboard.has_error_budget_panel` - Boolean for error budget visualization
  * Policy: Assert that dashboard includes SLO information for services with defined SLOs
  * Configuration: None

---

## Observability - Distributed Tracing

### Tracing Configuration

* **Distributed tracing is configured**: Services must have distributed tracing instrumented for request flow visibility.
  * Collector(s): Check application configuration for tracing setup (OpenTelemetry, Jaeger, Zipkin), or verify tracing library dependencies
  * Component JSON:
    * `.observability.tracing.configured` - Boolean for tracing configuration
    * `.observability.tracing.library` - Tracing library used (opentelemetry, jaeger-client, zipkin)
    * `.observability.tracing.exporter` - Trace exporter destination
  * Policy: Assert that distributed tracing is configured
  * Configuration: Acceptable tracing libraries

* **Tracing uses OpenTelemetry standard**: Services should use OpenTelemetry for vendor-neutral tracing instrumentation.
  * Collector(s): Check dependencies for OpenTelemetry SDK, or analyze tracing configuration
  * Component JSON:
    * `.observability.tracing.uses_opentelemetry` - Boolean for OpenTelemetry usage
    * `.observability.tracing.library` - Tracing library used
  * Policy: Assert that OpenTelemetry is used for tracing
  * Configuration: Whether OpenTelemetry is required or just preferred

* **Trace sampling rate is appropriate**: Trace sampling should balance visibility with cost and performance.
  * Collector(s): Parse tracing configuration for sampling settings
  * Component JSON:
    * `.observability.tracing.sampling_rate` - Configured sampling rate (0.0-1.0)
    * `.observability.tracing.sampling_type` - Sampling strategy (probabilistic, rate-limiting, adaptive)
  * Policy: Assert that sampling rate is within acceptable bounds
  * Configuration: Min/max sampling rate (default: 0.01-1.0)

* **Traces include required attributes**: Traces should include standard attributes for consistent analysis.
  * Collector(s): Analyze tracing configuration for resource attributes
  * Component JSON:
    * `.observability.tracing.resource_attributes` - Array of configured resource attributes
    * `.observability.tracing.has_required_attributes` - Boolean for required attributes presence
  * Policy: Assert that traces include required attributes
  * Configuration: Required trace attributes (default: ["service.name", "service.version", "deployment.environment"])

* **Trace context is propagated**: Services must propagate trace context to downstream services for end-to-end tracing.
  * Collector(s): Check tracing configuration for context propagation settings
  * Component JSON:
    * `.observability.tracing.context_propagation` - Boolean for context propagation enabled
    * `.observability.tracing.propagation_format` - Propagation format (w3c, b3, jaeger)
  * Policy: Assert that trace context propagation is configured
  * Configuration: Required propagation format (default: "w3c")

---

## Health Checks & Probes

### Health Endpoint Configuration

* **Health check endpoint exists**: Services must expose a health check endpoint for orchestrator and load balancer probes.
  * Collector(s): Parse application configuration for health endpoint, or probe common health paths in CI
  * Component JSON:
    * `.observability.health.endpoint_exists` - Boolean for health endpoint presence
    * `.observability.health.endpoint_path` - Health endpoint path (e.g., /health, /healthz)
  * Policy: Assert that health check endpoint is configured
  * Configuration: Expected health endpoint paths (default: ["/health", "/healthz", "/ready"])

* **Health check endpoint reflects true service health**: Health checks should verify actual service functionality, not just process liveness.
  * Collector(s): Analyze health endpoint implementation or configuration for dependency checks
  * Component JSON:
    * `.observability.health.checks_dependencies` - Boolean for dependency health checks
    * `.observability.health.dependencies_checked` - Array of dependencies verified in health check
    * `.observability.health.is_deep_health_check` - Boolean for comprehensive health check
  * Policy: Assert that health check verifies critical dependencies
  * Configuration: Required dependency types to check (default: ["database", "cache"])

* **Liveness and readiness probes are distinct**: Services should have separate liveness (is process alive) and readiness (can accept traffic) probes.
  * Collector(s): Parse Kubernetes manifests for probe configurations, or check application for separate endpoints
  * Component JSON:
    * `.observability.health.has_liveness_endpoint` - Boolean for liveness endpoint
    * `.observability.health.has_readiness_endpoint` - Boolean for readiness endpoint
    * `.observability.health.probes_are_distinct` - Boolean for distinct probe endpoints
  * Policy: Assert that liveness and readiness probes are configured separately
  * Configuration: None

* **Readiness probe checks dependency availability**: Readiness probes should verify that critical dependencies are accessible.
  * Collector(s): Analyze readiness probe endpoint implementation or configuration
  * Component JSON:
    * `.observability.health.readiness_checks_dependencies` - Boolean for dependency verification
    * `.observability.health.readiness_dependencies` - Array of dependencies checked
  * Policy: Assert that readiness probe verifies dependencies
  * Configuration: Required dependencies for readiness check

* **Health check response time is monitored**: Health check latency should be monitored to detect degradation.
  * Collector(s): Query monitoring system for health check latency metrics
  * Component JSON:
    * `.observability.health.latency_monitored` - Boolean for latency monitoring
    * `.observability.health.latency_metric_name` - Name of health check latency metric
  * Policy: Assert that health check latency is tracked
  * Configuration: None

---

## Alerting

### Alert Configuration

* **Alerts are configured for the service**: Production services must have alerts configured for key failure scenarios.
  * Collector(s): Query monitoring system API for alerts/monitors associated with the service
  * Component JSON:
    * `.observability.alerts.configured` - Boolean for alert configuration
    * `.observability.alerts.count` - Number of alerts configured
    * `.observability.alerts.list` - Array of configured alert definitions
  * Policy: Assert that alerts are configured for production services
  * Configuration: Minimum number of alerts (default: 3)

* **Critical alerts route to on-call**: High-severity alerts must route to the on-call responder via incident management integration.
  * Collector(s): Query monitoring system for alert routing configuration, verify integration with PagerDuty/OpsGenie
  * Component JSON:
    * `.observability.alerts.critical_to_oncall` - Boolean for critical alert routing
    * `.observability.alerts.oncall_integration` - Incident management integration details
  * Policy: Assert that critical alerts route to on-call
  * Configuration: Alert severity levels requiring on-call routing

* **Alerts include runbook links**: Alert definitions should include links to relevant runbook sections for responders.
  * Collector(s): Query monitoring system for alert annotations/descriptions
  * Component JSON:
    * `.observability.alerts.have_runbook_links` - Boolean for runbook links in alerts
    * `.observability.alerts.alerts_without_runbooks` - Array of alerts missing runbook links
  * Policy: Assert that alerts include runbook links
  * Configuration: Required runbook link format

* **SLO-based alerts are configured**: Services should have alerts triggered by SLO error budget consumption.
  * Collector(s): Query monitoring system for SLO burn rate or error budget alerts
  * Component JSON:
    * `.observability.alerts.has_slo_alerts` - Boolean for SLO-based alerts
    * `.observability.alerts.slo_burn_rate_alerts` - Array of burn rate alert definitions
  * Policy: Assert that SLO-based alerts are configured for services with defined SLOs
  * Configuration: Required burn rate thresholds (default: [2%, 5%, 10% per hour])

* **Alert thresholds are tuned appropriately**: Alert thresholds should be based on historical data and SLOs to minimize false positives.
  * Collector(s): Query monitoring system for alert trigger history and false positive rates
  * Component JSON:
    * `.observability.alerts.false_positive_rate` - False positive rate percentage
    * `.observability.alerts.alert_fatigue_risk` - Boolean for high alert volume
  * Policy: Assert that alert false positive rate is below threshold
  * Configuration: Maximum false positive rate (default: 10%)

* **Alerts have appropriate severity levels**: Alerts should be classified by severity to enable appropriate response.
  * Collector(s): Query monitoring system for alert severity configurations
  * Component JSON:
    * `.observability.alerts.by_severity` - Count of alerts by severity level
    * `.observability.alerts.has_severity_classification` - Boolean for severity on all alerts
  * Policy: Assert that all alerts have severity classification
  * Configuration: Required severity levels (default: ["critical", "warning", "info"])

### Alert Fatigue Prevention

* **Alert volume is manageable**: The number of alerts should not overwhelm on-call responders.
  * Collector(s): Query incident management system for alert/incident volume over time
  * Component JSON:
    * `.oncall.alert_volume.weekly_alerts` - Average weekly alert count
    * `.oncall.alert_volume.daily_alerts` - Average daily alert count
    * `.oncall.alert_volume.is_excessive` - Boolean for excessive alert volume
  * Policy: Assert that alert volume is below fatigue threshold
  * Configuration: Maximum weekly alerts (default: 50)

* **Alerts are deduplicated**: Multiple related alerts should be deduplicated to reduce noise.
  * Collector(s): Check monitoring/incident system configuration for deduplication rules
  * Component JSON:
    * `.observability.alerts.deduplication_configured` - Boolean for deduplication setup
    * `.observability.alerts.deduplication_rules` - Array of deduplication rules
  * Policy: Assert that alert deduplication is configured
  * Configuration: None

* **Alert grouping is configured**: Related alerts should be grouped into incidents to reduce cognitive load.
  * Collector(s): Check incident management system for alert grouping/correlation rules
  * Component JSON:
    * `.observability.alerts.grouping_configured` - Boolean for alert grouping
    * `.observability.alerts.grouping_rules` - Array of grouping rules
  * Policy: Assert that alert grouping is configured
  * Configuration: None

---

## Disaster Recovery & Resilience

### Disaster Recovery Procedures

* **Disaster recovery plan is documented**: Services must have documented disaster recovery procedures.
  * Collector(s): Check for DR documentation in standard locations (docs/disaster-recovery.md) or catalog annotations
  * Component JSON:
    * `.oncall.disaster_recovery.plan_exists` - Boolean for DR plan presence
    * `.oncall.disaster_recovery.plan_path` - Path to DR documentation
    * `.oncall.disaster_recovery.plan_url` - URL to external DR documentation
  * Policy: Assert that DR plan is documented for production services
  * Configuration: Expected DR documentation locations

* **DR plan was reviewed recently**: Disaster recovery plans must be reviewed and updated periodically.
  * Collector(s): Parse DR documentation for review date, or check file modification timestamp
  * Component JSON:
    * `.oncall.disaster_recovery.last_reviewed` - ISO 8601 timestamp of last review
    * `.oncall.disaster_recovery.days_since_review` - Days since last review
    * `.oncall.disaster_recovery.review_is_current` - Boolean for current review
  * Policy: Assert that DR plan was reviewed within threshold
  * Configuration: Maximum days since review (default: 180)

* **Recovery time objective (RTO) is defined**: Services must have a defined RTO indicating acceptable downtime.
  * Collector(s): Parse DR documentation or catalog annotations for RTO
  * Component JSON:
    * `.oncall.disaster_recovery.rto_defined` - Boolean for RTO definition
    * `.oncall.disaster_recovery.rto_minutes` - RTO in minutes
  * Policy: Assert that RTO is defined for production services
  * Configuration: Tags requiring RTO definition

* **Recovery point objective (RPO) is defined**: Services with data persistence must have a defined RPO indicating acceptable data loss.
  * Collector(s): Parse DR documentation or catalog annotations for RPO
  * Component JSON:
    * `.oncall.disaster_recovery.rpo_defined` - Boolean for RPO definition
    * `.oncall.disaster_recovery.rpo_minutes` - RPO in minutes
  * Policy: Assert that RPO is defined for services with persistent data
  * Configuration: Tags requiring RPO definition (e.g., ["database", "stateful"])

### Backup & Recovery Testing

* **Backup verification is performed regularly**: Data backups must be tested periodically to ensure recoverability.
  * Collector(s): Check for backup verification documentation with timestamps, or query backup system API
  * Component JSON:
    * `.oncall.backup.verification_documented` - Boolean for verification documentation
    * `.oncall.backup.last_verification_date` - ISO 8601 timestamp of last verification
    * `.oncall.backup.days_since_verification` - Days since last backup test
  * Policy: Assert that backup verification was performed within threshold
  * Configuration: Maximum days between verifications (default: 90)

* **Recovery procedures are tested regularly**: Disaster recovery procedures must be tested periodically through drills.
  * Collector(s): Check for recovery drill documentation with timestamps
  * Component JSON:
    * `.oncall.disaster_recovery.drill_documented` - Boolean for drill documentation
    * `.oncall.disaster_recovery.last_drill_date` - ISO 8601 timestamp of last drill
    * `.oncall.disaster_recovery.days_since_drill` - Days since last DR drill
  * Policy: Assert that DR drill was conducted within threshold
  * Configuration: Maximum days between drills (default: 180)

* **Game day exercises are conducted**: Teams should conduct game day exercises to practice incident response.
  * Collector(s): Check for game day documentation with timestamps
  * Component JSON:
    * `.oncall.game_day.documented` - Boolean for game day documentation
    * `.oncall.game_day.last_exercise_date` - ISO 8601 timestamp of last game day
    * `.oncall.game_day.days_since_exercise` - Days since last game day
  * Policy: Assert that game day was conducted within threshold
  * Configuration: Maximum days between game days (default: 365)

### Resilience Patterns

* **Circuit breaker is implemented for external calls**: Services should implement circuit breakers for calls to external dependencies.
  * Collector(s): Check dependencies for circuit breaker libraries, or analyze configuration for circuit breaker setup
  * Component JSON:
    * `.observability.resilience.circuit_breaker_configured` - Boolean for circuit breaker
    * `.observability.resilience.circuit_breaker_library` - Library used (hystrix, resilience4j, polly)
    * `.observability.resilience.protected_dependencies` - Array of dependencies with circuit breakers
  * Policy: Assert that circuit breakers are configured for services with external dependencies
  * Configuration: Required circuit breaker library per language

* **Retry logic with backoff is implemented**: Services should implement retries with exponential backoff for transient failures.
  * Collector(s): Check code or configuration for retry patterns
  * Component JSON:
    * `.observability.resilience.retry_configured` - Boolean for retry logic
    * `.observability.resilience.uses_exponential_backoff` - Boolean for backoff pattern
  * Policy: Assert that retry logic is configured for services with external calls
  * Configuration: None

* **Timeouts are configured for external calls**: All external service calls must have appropriate timeouts configured.
  * Collector(s): Check application configuration for timeout settings
  * Component JSON:
    * `.observability.resilience.timeouts_configured` - Boolean for timeout configuration
    * `.observability.resilience.default_timeout_ms` - Default timeout value
  * Policy: Assert that timeouts are configured for external calls
  * Configuration: Maximum allowed timeout (default: 30000ms)

* **Graceful degradation is implemented**: Services should degrade gracefully when dependencies are unavailable.
  * Collector(s): Check for fallback configurations or degradation documentation
  * Component JSON:
    * `.observability.resilience.graceful_degradation` - Boolean for degradation support
    * `.observability.resilience.fallback_behaviors` - Array of documented fallback behaviors
  * Policy: Assert that graceful degradation is documented for critical services
  * Configuration: Tags requiring graceful degradation

---

## Capacity Planning

### Load Projections

* **Capacity requirements are documented**: Services should have documented capacity requirements and scaling factors.
  * Collector(s): Check for capacity documentation in standard locations
  * Component JSON:
    * `.oncall.capacity.requirements_documented` - Boolean for capacity documentation
    * `.oncall.capacity.documentation_path` - Path to capacity documentation
  * Policy: Assert that capacity requirements are documented for production services
  * Configuration: Expected documentation locations

* **Traffic projections are maintained**: Services should have traffic projections for capacity planning.
  * Collector(s): Check for traffic projection documentation or capacity planning artifacts
  * Component JSON:
    * `.oncall.capacity.projections_documented` - Boolean for projection documentation
    * `.oncall.capacity.projected_growth_percentage` - Projected traffic growth percentage
  * Policy: Assert that traffic projections are documented
  * Configuration: Tags requiring traffic projections

* **Scaling thresholds are defined**: Auto-scaling configurations should have appropriate thresholds based on capacity planning.
  * Collector(s): Parse HPA or auto-scaling configurations for threshold values
  * Component JSON:
    * `.oncall.capacity.scaling_thresholds_defined` - Boolean for threshold definition
    * `.oncall.capacity.scale_up_threshold` - CPU/memory threshold for scaling up
    * `.oncall.capacity.scale_down_threshold` - Threshold for scaling down
  * Policy: Assert that scaling thresholds are explicitly defined
  * Configuration: Required threshold types (cpu, memory, custom metrics)

### Resource Monitoring

* **Resource utilization is monitored**: Services must have resource utilization monitoring for capacity planning.
  * Collector(s): Query monitoring system for resource utilization metrics and dashboards
  * Component JSON:
    * `.oncall.capacity.utilization_monitored` - Boolean for utilization monitoring
    * `.oncall.capacity.utilization_metrics` - Array of monitored resource types
  * Policy: Assert that resource utilization is monitored
  * Configuration: Required resource types (default: ["cpu", "memory", "disk", "network"])

* **Resource utilization alerts are configured**: Alerts should fire when resource utilization approaches capacity limits.
  * Collector(s): Query monitoring system for resource-based alerts
  * Component JSON:
    * `.oncall.capacity.utilization_alerts_configured` - Boolean for utilization alerts
    * `.oncall.capacity.alert_thresholds` - Configured alert thresholds
  * Policy: Assert that resource utilization alerts are configured
  * Configuration: Required alert thresholds (default: 70%, 85%, 95%)

---

## Anomaly Detection

### Anomaly Detection Configuration

* **Anomaly detection is configured for key metrics**: Services should have anomaly detection enabled for critical metrics.
  * Collector(s): Query monitoring system for anomaly detection configurations (Datadog anomaly monitors, Prometheus anomaly detection rules)
  * Component JSON:
    * `.observability.anomaly_detection.configured` - Boolean for anomaly detection setup
    * `.observability.anomaly_detection.metrics_monitored` - Array of metrics with anomaly detection
    * `.observability.anomaly_detection.tool` - Anomaly detection tool used
  * Policy: Assert that anomaly detection is configured for production services
  * Configuration: Required metrics for anomaly detection (default: ["latency", "error_rate", "traffic"])

* **Baseline metrics are established**: Anomaly detection requires established baselines for comparison.
  * Collector(s): Query monitoring system for baseline/historical data availability
  * Component JSON:
    * `.observability.anomaly_detection.baseline_established` - Boolean for baseline data
    * `.observability.anomaly_detection.baseline_duration_days` - Duration of baseline data
  * Policy: Assert that metrics have sufficient baseline data for anomaly detection
  * Configuration: Minimum baseline duration (default: 14 days)

* **Deployment anomaly detection is enabled**: Services should have detection for deployment-related anomalies.
  * Collector(s): Check for deployment markers in monitoring and associated anomaly detection
  * Component JSON:
    * `.observability.anomaly_detection.deployment_markers` - Boolean for deployment event markers
    * `.observability.anomaly_detection.deployment_anomaly_detection` - Boolean for deployment-specific detection
  * Policy: Assert that deployment anomaly detection is configured
  * Configuration: None

---

## Summary Policies

* **On-call readiness is complete**: Aggregate check that all on-call requirements are met.
  * Collector(s): Aggregate on-call configuration checks
  * Component JSON:
    * `.oncall.summary.has_oncall` - On-call schedule exists
    * `.oncall.summary.has_escalation` - Escalation policy exists
    * `.oncall.summary.has_runbook` - Runbook exists
    * `.oncall.summary.has_sla` - SLA is defined
    * `.oncall.summary.oncall_ready` - Boolean for aggregate on-call readiness
  * Policy: Assert that aggregate on-call readiness is achieved
  * Configuration: Which on-call components are required

* **Observability is complete**: Aggregate check that all observability requirements are met.
  * Collector(s): Aggregate observability configuration checks
  * Component JSON:
    * `.observability.summary.has_logging` - Structured logging configured
    * `.observability.summary.has_metrics` - Metrics endpoint configured
    * `.observability.summary.has_tracing` - Distributed tracing configured
    * `.observability.summary.has_dashboard` - Dashboard exists
    * `.observability.summary.has_alerts` - Alerts are configured
    * `.observability.summary.golden_signals_complete` - All golden signals monitored
    * `.observability.summary.fully_observable` - Boolean for full observability
  * Policy: Assert that aggregate observability requirements are met
  * Configuration: Which observability components are required per tier

* **Resilience posture is adequate**: Aggregate check that resilience patterns are implemented.
  * Collector(s): Aggregate resilience configuration checks
  * Component JSON:
    * `.observability.resilience.has_circuit_breakers` - Circuit breakers configured
    * `.observability.resilience.has_timeouts` - Timeouts configured
    * `.observability.resilience.has_retries` - Retry logic configured
    * `.observability.resilience.resilience_score` - Numeric resilience score
  * Policy: Assert that resilience score meets threshold
  * Configuration: Minimum resilience score, required resilience patterns per tier
