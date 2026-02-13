# Operational Readiness Guardrails

This document specifies possible policies for the **Operational Readiness** category. These guardrails cover documentation and runbooks, on-call and incident management, observability (logging, metrics, tracing), health checks, alerting, disaster recovery, capacity planning, and anomaly detection.

---

## Documentation & Knowledge Base

### Runbooks

* `ops-runbook-exists` **Runbook exists for the service**: Every production service must have a runbook documenting operational procedures, troubleshooting steps, and escalation paths.
  * Collector(s): Check for runbook file in standard locations (docs/runbook.md, runbook/), or verify runbook URL in catalog annotations or README
  * Component JSON:
    * `.oncall.runbook.exists` - Boolean indicating runbook presence
    * `.oncall.runbook.path` - Path to runbook file if in repository
    * `.oncall.runbook.url` - URL to external runbook if hosted elsewhere
    * `.oncall.runbook.source` - Where runbook was discovered (file, catalog, readme)
  * Policy: Assert that a runbook exists either in the repository or is linked from the service catalog
  * Configuration: Expected runbook locations, acceptable external wiki patterns
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `ops-runbook-required-sections` **Runbook contains required sections**: Runbooks must include standard sections covering common operational scenarios.
  * Collector(s): Parse runbook file (Markdown) and extract section headings for comparison against required sections
  * Component JSON:
    * `.oncall.runbook.sections` - Array of section headings found in runbook
    * `.oncall.runbook.has_required_sections` - Boolean for all required sections present
    * `.oncall.runbook.missing_sections` - Array of missing required sections
  * Policy: Assert that all required sections are present in the runbook
  * Configuration: Required section names (default: ["Overview", "Architecture", "Dependencies", "Common Issues", "Troubleshooting", "Escalation", "Recovery Procedures"])
  * Strategy: Strategy 7 (LLM-Assisted Analysis) or Strategy 8 (File Parsing and Schema Extraction)

* `ops-runbook-recent-update` **Runbook was updated recently**: Runbooks must be kept up-to-date to remain useful during incidents.
  * Collector(s): Check file modification timestamp for runbook, or query wiki API for last update time
  * Component JSON:
    * `.oncall.runbook.last_updated` - ISO 8601 timestamp of last runbook update
    * `.oncall.runbook.days_since_update` - Days since last update
    * `.oncall.runbook.is_stale` - Boolean indicating runbook is stale
  * Policy: Assert that runbook was updated within the configured threshold
  * Configuration: Maximum days since update (default: 90)
  * Strategy: Strategy 14 (Historical Trend Analysis via Component JSON History)

* `ops-runbook-catalog-linked` **Runbook is linked from service catalog**: The runbook URL should be registered in the service catalog for discoverability during incidents.
  * Collector(s): Parse service catalog entry (Backstage catalog-info.yaml) for runbook annotation
  * Component JSON:
    * `.catalog.annotations.runbook` - Runbook URL from catalog annotation
    * `.catalog.annotations.runbook_exists` - Boolean for runbook annotation presence
  * Policy: Assert that runbook annotation is present in service catalog
  * Configuration: Expected annotation key (default: "runbook" or "docs/runbook")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### SLA/SLO Documentation

* `ops-sla-defined` **SLA is defined for the service**: Production services must have documented Service Level Agreements defining availability and performance commitments.
  * Collector(s): Check for SLA definition in catalog annotations, dedicated SLA file, or README section
  * Component JSON:
    * `.oncall.sla.defined` - Boolean indicating SLA is defined
    * `.oncall.sla.uptime_percentage` - Documented uptime commitment (e.g., 99.9)
    * `.oncall.sla.response_time_ms` - Documented response time SLA in milliseconds
    * `.oncall.sla.source` - Where SLA was discovered (catalog, file, readme)
  * Policy: Assert that SLA is defined for production services
  * Configuration: Tags requiring SLA (default: ["production", "tier1", "tier2"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `ops-slos-defined` **SLOs are defined with error budgets**: Services should have Service Level Objectives with measurable targets and error budgets.
  * Collector(s): Check for SLO definitions in catalog, dedicated SLO files, or monitoring configuration (Prometheus SLO rules, Datadog SLO monitors)
  * Component JSON:
    * `.oncall.slo.defined` - Boolean indicating SLOs are defined
    * `.oncall.slo.objectives` - Array of SLO definitions with targets
    * `.oncall.slo.has_error_budget` - Boolean for error budget definition
    * `.oncall.slo.error_budget_percentage` - Error budget percentage
  * Policy: Assert that SLOs are defined with error budgets for production services
  * Configuration: Required SLO types (default: ["availability", "latency"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

* `ops-slo-dashboard` **SLO dashboard exists**: SLO progress and error budget consumption should be visualized in a dashboard.
  * Collector(s): Check catalog annotations for SLO dashboard link, or query monitoring system API for SLO dashboard existence
  * Component JSON:
    * `.oncall.slo.dashboard_exists` - Boolean for SLO dashboard presence
    * `.oncall.slo.dashboard_url` - URL to SLO dashboard
  * Policy: Assert that SLO dashboard exists and is linked
  * Configuration: None
  * Strategy: Strategy 10 (External Vendor API Integration)

### Architecture Documentation

* `ops-architecture-diagram` **Architecture diagram exists**: Services must have architecture diagrams showing component relationships and data flows.
  * Collector(s): Check for architecture diagram files (PNG, SVG, draw.io, Mermaid) in docs/ folder or linked from README
  * Component JSON:
    * `.repo.documentation.architecture_diagram_exists` - Boolean for diagram presence
    * `.repo.documentation.architecture_diagram_path` - Path to diagram file
    * `.repo.documentation.architecture_diagram_format` - Diagram format (image, mermaid, drawio)
  * Policy: Assert that architecture diagram exists
  * Configuration: Accepted diagram file patterns, accepted formats
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `ops-dependency-docs` **Dependency documentation is current**: Service dependencies (upstream and downstream) must be documented and kept current.
  * Collector(s): Parse catalog-info.yaml for dependency declarations, or extract from architecture documentation
  * Component JSON:
    * `.catalog.dependencies` - Array of declared service dependencies
    * `.catalog.apis.consumes` - APIs consumed by the service
    * `.catalog.apis.provides` - APIs provided by the service
    * `.catalog.dependencies_documented` - Boolean for dependency documentation presence
  * Policy: Assert that service dependencies are documented in the catalog
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## On-Call & Incident Management

### On-Call Schedule

* `oncall-schedule-configured` **On-call schedule is configured**: Production services must have an on-call schedule configured in the incident management system (PagerDuty, OpsGenie, VictorOps).
  * Collector(s): Query PagerDuty/OpsGenie API using service ID from catalog annotations to verify schedule exists
  * Component JSON:
    * `.oncall.schedule.exists` - Boolean indicating schedule is configured
    * `.oncall.schedule.id` - Schedule ID in incident management system
    * `.oncall.schedule.name` - Schedule name
    * `.oncall.source.tool` - Incident management tool (pagerduty, opsgenie, victorops)
  * Policy: Assert that on-call schedule is configured for production services
  * Configuration: Tags requiring on-call (default: ["production"])
  * Strategy: Strategy 10 (External Vendor API Integration)

* `oncall-min-participants` **On-call schedule has minimum participants**: On-call rotations must have a minimum number of participants to avoid burnout and ensure coverage.
  * Collector(s): Query incident management API to get schedule participant count
  * Component JSON:
    * `.oncall.schedule.participants` - Number of people in the rotation
    * `.oncall.schedule.participant_list` - Array of participant identifiers
    * `.oncall.summary.min_participants` - Minimum participant count found
  * Policy: Assert that on-call rotation has at least the minimum required participants
  * Configuration: Minimum participants (default: 4)
  * Strategy: Strategy 10 (External Vendor API Integration)

* `oncall-24x7-coverage` **On-call schedule covers 24/7**: Production services must have continuous on-call coverage without gaps.
  * Collector(s): Query incident management API to analyze schedule coverage
  * Component JSON:
    * `.oncall.schedule.coverage_percentage` - Percentage of time covered by schedule
    * `.oncall.schedule.has_gaps` - Boolean indicating coverage gaps exist
    * `.oncall.schedule.gap_hours` - Total hours of gaps in coverage
  * Policy: Assert that schedule provides 100% coverage (24/7)
  * Configuration: Minimum coverage percentage (default: 100)
  * Strategy: Strategy 10 (External Vendor API Integration)

* `oncall-rotation-length` **On-call rotation length is appropriate**: Rotation shifts should not be too long to prevent fatigue, nor too short to prevent disruption.
  * Collector(s): Query incident management API to get rotation configuration
  * Component JSON:
    * `.oncall.schedule.rotation` - Rotation type (daily, weekly, custom)
    * `.oncall.schedule.shift_length_hours` - Length of each shift in hours
    * `.oncall.schedule.rotation_length_days` - Length of rotation cycle in days
  * Policy: Assert that shift and rotation lengths are within acceptable bounds
  * Configuration: Min/max shift length (default: 12-168 hours), min/max rotation length (default: 7-14 days)
  * Strategy: Strategy 10 (External Vendor API Integration)

* `oncall-backup-coverage` **On-call schedule has backup/secondary coverage**: Critical services should have secondary on-call coverage for escalation.
  * Collector(s): Query incident management API to check for secondary/backup schedule
  * Component JSON:
    * `.oncall.schedule.has_secondary` - Boolean for secondary schedule existence
    * `.oncall.schedule.secondary_id` - Secondary schedule ID
    * `.oncall.schedule.secondary_participants` - Participants in secondary rotation
  * Policy: Assert that secondary on-call coverage exists for critical services
  * Configuration: Tags requiring secondary coverage (default: ["tier1", "critical"])
  * Strategy: Strategy 10 (External Vendor API Integration)

### Escalation Policies

* `oncall-escalation-policy` **Escalation policy is configured**: Services must have an escalation policy defining how incidents escalate when unacknowledged.
  * Collector(s): Query incident management API for escalation policy associated with the service
  * Component JSON:
    * `.oncall.escalation.exists` - Boolean for escalation policy presence
    * `.oncall.escalation.id` - Escalation policy ID
    * `.oncall.escalation.name` - Escalation policy name
  * Policy: Assert that escalation policy is configured for production services
  * Configuration: None
  * Strategy: Strategy 10 (External Vendor API Integration)

* `oncall-escalation-levels` **Escalation policy has multiple levels**: Escalation policies must have multiple levels to ensure incidents are handled even if primary responders are unavailable.
  * Collector(s): Query incident management API to get escalation policy details
  * Component JSON:
    * `.oncall.escalation.levels` - Number of escalation levels
    * `.oncall.escalation.level_details` - Array of escalation level configurations
    * `.oncall.escalation.final_level_is_management` - Boolean for management in final level
  * Policy: Assert that escalation policy has at least the minimum required levels
  * Configuration: Minimum escalation levels (default: 3)
  * Strategy: Strategy 10 (External Vendor API Integration)

* `oncall-escalation-timeouts` **Escalation timeouts are appropriate**: Escalation timeouts should be short enough to ensure timely response but not so short as to cause alert fatigue.
  * Collector(s): Query incident management API for escalation timeout configuration
  * Component JSON:
    * `.oncall.escalation.timeout_minutes` - Timeout before escalation at each level
    * `.oncall.escalation.total_escalation_time` - Total time before reaching final level
  * Policy: Assert that escalation timeouts are within acceptable ranges
  * Configuration: Min/max timeout per level (default: 5-30 minutes), max total escalation time (default: 60 minutes)
  * Strategy: Strategy 10 (External Vendor API Integration)

* `oncall-escalation-management` **Escalation policy includes management for critical incidents**: Critical incident escalation paths should include management notification.
  * Collector(s): Query incident management API and verify management targets in escalation levels
  * Component JSON:
    * `.oncall.escalation.includes_management` - Boolean for management in escalation chain
    * `.oncall.escalation.management_level` - Level at which management is engaged
  * Policy: Assert that management is included in escalation for critical services
  * Configuration: Tags requiring management escalation (default: ["tier1", "critical"])
  * Strategy: Strategy 10 (External Vendor API Integration)

### Team & HRIS Integration

* `oncall-active-employees` **On-call participants are active employees**: On-call schedule participants should be validated against HRIS/HR system to ensure they are current employees.
  * Collector(s): Query incident management API for participants, then cross-reference with HRIS API (Workday, BambooHR, etc.)
  * Component JSON:
    * `.oncall.schedule.participant_list` - Array of participant identifiers
    * `.oncall.schedule.inactive_participants` - Array of participants not found in HRIS
    * `.oncall.schedule.all_participants_active` - Boolean for all participants validated
  * Policy: Assert that all on-call participants are active employees
  * Configuration: HRIS system to validate against
  * Strategy: Strategy 10 (External Vendor API Integration)

* `oncall-matches-ownership` **On-call team matches service ownership**: The on-call team should align with the team that owns the service in the catalog.
  * Collector(s): Compare service owner from catalog with on-call schedule team assignment
  * Component JSON:
    * `.catalog.entity.owner` - Service owner from catalog
    * `.oncall.schedule.team` - Team associated with on-call schedule
    * `.oncall.ownership_aligned` - Boolean for ownership alignment
  * Policy: Assert that on-call team aligns with service ownership
  * Configuration: None
  * Strategy: Strategy 10 (External Vendor API Integration)

* `oncall-hris-correlation` **Catalog team correlates with HRIS**: Service ownership teams in the catalog should exist in the HRIS/HR system.
  * Collector(s): Query HRIS API to validate team names/IDs from catalog
  * Component JSON:
    * `.catalog.entity.owner` - Team owner from catalog
    * `.catalog.owner_exists_in_hris` - Boolean for team validation
    * `.catalog.hris_team_id` - Corresponding HRIS team ID
  * Policy: Assert that catalog team exists in HRIS
  * Configuration: HRIS integration details
  * Strategy: Strategy 10 (External Vendor API Integration)

### Incident Management Integration

* `oncall-service-registered` **Service is registered in incident management system**: The service must be registered in PagerDuty/OpsGenie with proper routing.
  * Collector(s): Query incident management API to verify service exists with the expected identifier
  * Component JSON:
    * `.oncall.service.exists` - Boolean for service registration
    * `.oncall.service.id` - Service ID in incident management system
    * `.oncall.service.integration_key` - Integration key for alerting
  * Policy: Assert that service is registered in incident management system
  * Configuration: Expected service naming pattern
  * Strategy: Strategy 10 (External Vendor API Integration)

* `oncall-catalog-linked` **Incident management service is linked from catalog**: The incident management service ID should be documented in the service catalog for quick access.
  * Collector(s): Parse catalog annotations for PagerDuty/OpsGenie service reference
  * Component JSON:
    * `.catalog.annotations.pagerduty_service` - PagerDuty service ID from catalog
    * `.catalog.annotations.opsgenie_team` - OpsGenie team from catalog
    * `.catalog.annotations.incident_service_linked` - Boolean for any incident service annotation
  * Policy: Assert that incident management service is linked in catalog
  * Configuration: Expected annotation keys
  * Strategy: Strategy 10 (External Vendor API Integration)

* `oncall-communication-channel` **Service has incident communication channel**: Services should have a designated communication channel (Slack, Teams) for incident coordination.
  * Collector(s): Parse catalog annotations for Slack channel reference
  * Component JSON:
    * `.catalog.annotations.slack_channel` - Slack channel from catalog
    * `.catalog.annotations.teams_channel` - Microsoft Teams channel from catalog
    * `.catalog.annotations.has_incident_channel` - Boolean for incident channel presence
  * Policy: Assert that incident communication channel is documented
  * Configuration: Expected annotation keys
  * Strategy: Strategy 10 (External Vendor API Integration)

---

## Observability - Logging

### Logging Configuration

* `logging-structured` **Structured logging is configured**: Applications must use structured logging (JSON format) for machine-parseable log output.
  * Collector(s): Analyze application configuration files for logging framework settings, or parse log output samples from CI
  * Component JSON:
    * `.observability.logging.configured` - Boolean for logging configuration presence
    * `.observability.logging.structured` - Boolean for structured logging format
    * `.observability.logging.format` - Log format (json, text, logfmt)
    * `.observability.logging.framework` - Logging framework used
  * Policy: Assert that structured logging is configured
  * Configuration: Acceptable log formats (default: ["json", "logfmt"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `logging-approved-library` **Logging uses approved library**: Applications should use organization-approved logging libraries for consistency.
  * Collector(s): Parse dependency files for logging library dependencies, or check configuration for logging framework
  * Component JSON:
    * `.observability.logging.framework` - Logging framework/library used
    * `.observability.logging.is_approved_library` - Boolean for approved library usage
  * Policy: Assert that logging uses an approved library
  * Configuration: Approved logging libraries per language (e.g., Go: ["zap", "zerolog"], Python: ["structlog", "python-json-logger"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `logging-levels-configured` **Log levels are appropriately configured**: Production logging should use appropriate log levels (not DEBUG in production).
  * Collector(s): Parse application configuration for log level settings
  * Component JSON:
    * `.observability.logging.level` - Configured log level
    * `.observability.logging.level_configurable` - Boolean for runtime configurability
  * Policy: Assert that log level is not too verbose for production (not DEBUG)
  * Configuration: Minimum log level for production (default: INFO)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `logging-correlation-ids` **Logs include correlation IDs**: Logs must include request/trace correlation IDs for distributed tracing integration.
  * Collector(s): Analyze logging configuration or sample logs for correlation ID fields
  * Component JSON:
    * `.observability.logging.has_correlation_id` - Boolean for correlation ID presence
    * `.observability.logging.correlation_id_field` - Field name for correlation ID
  * Policy: Assert that logs include correlation/trace IDs
  * Configuration: Expected correlation ID field names (default: ["trace_id", "request_id", "correlation_id"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `logging-context-fields` **Logs include required context fields**: Logs should include standard context fields for consistent querying and analysis.
  * Collector(s): Analyze logging configuration for included context fields
  * Component JSON:
    * `.observability.logging.context_fields` - Array of configured context fields
    * `.observability.logging.has_required_fields` - Boolean for all required fields present
    * `.observability.logging.missing_fields` - Array of missing required fields
  * Policy: Assert that logs include all required context fields
  * Configuration: Required context fields (default: ["service", "environment", "version", "timestamp", "level"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `logging-no-sensitive-data` **Sensitive data is excluded from logs**: Logs must not contain PII, credentials, or other sensitive information.
  * Collector(s): Analyze logging configuration for field filtering/masking, or scan log samples for sensitive patterns
  * Component JSON:
    * `.observability.logging.sensitive_field_masking` - Boolean for sensitive field masking configured
    * `.observability.logging.masked_fields` - Array of fields configured for masking
    * `.observability.logging.has_sensitive_data_risk` - Boolean for potential sensitive data in logs
  * Policy: Assert that sensitive data masking is configured
  * Configuration: Fields that should be masked (default: ["password", "token", "secret", "authorization", "credit_card"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Log Aggregation

* `logging-centralized` **Logs are shipped to centralized system**: Application logs must be shipped to a centralized log aggregation system (ELK, Splunk, Datadog, CloudWatch).
  * Collector(s): Check for log shipping configuration in application or infrastructure (Fluentd, Filebeat, Vector configs)
  * Component JSON:
    * `.observability.logging.aggregation_configured` - Boolean for log aggregation setup
    * `.observability.logging.aggregation_destination` - Destination system (elasticsearch, splunk, datadog)
    * `.observability.logging.log_shipper` - Log shipper used (fluentd, filebeat, vector)
  * Policy: Assert that log aggregation is configured
  * Configuration: Required aggregation destination
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `logging-retention` **Log retention meets compliance requirements**: Log retention periods must meet organizational and compliance requirements.
  * Collector(s): Query log aggregation system API for retention settings, or check IaC for log retention configuration
  * Component JSON:
    * `.observability.logging.retention_days` - Configured log retention in days
    * `.observability.logging.meets_retention_requirement` - Boolean for compliance
  * Policy: Assert that log retention meets minimum requirements
  * Configuration: Minimum retention days (default: 90), per-tag overrides for compliance
  * Strategy: Strategy 10 (External Vendor API Integration)

---

## Observability - Metrics

### Metrics Configuration

* `metrics-endpoint-exposed` **Application exposes metrics endpoint**: Applications must expose a metrics endpoint for scraping by monitoring systems.
  * Collector(s): Check application configuration for metrics endpoint, or probe the metrics endpoint in CI/CD
  * Component JSON:
    * `.observability.metrics.configured` - Boolean for metrics configuration
    * `.observability.metrics.endpoint` - Metrics endpoint path (e.g., /metrics)
    * `.observability.metrics.format` - Metrics format (prometheus, statsd, otlp)
  * Policy: Assert that metrics endpoint is configured
  * Configuration: Expected endpoint paths, accepted formats
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 15 (Runtime and Deployed State Verification)

* `metrics-k8s-declared` **Metrics endpoint is declared in Kubernetes**: Kubernetes workloads should have metrics annotations/labels for service discovery.
  * Collector(s): Parse Kubernetes manifests for Prometheus scrape annotations or ServiceMonitor resources
  * Component JSON:
    * `.k8s.workloads[].has_metrics_annotations` - Boolean for metrics annotations
    * `.k8s.workloads[].metrics_port` - Port exposed for metrics
    * `.k8s.workloads[].metrics_path` - Path for metrics endpoint
    * `.k8s.has_service_monitor` - Boolean for ServiceMonitor resource
  * Policy: Assert that metrics scraping is configured in Kubernetes
  * Configuration: Whether annotations or ServiceMonitor is required
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `metrics-golden-signals` **Golden signals are monitored**: Services must monitor the four golden signals (latency, traffic, errors, saturation).
  * Collector(s): Query monitoring system for metrics matching golden signal patterns, or analyze metrics configuration
  * Component JSON:
    * `.observability.metrics.golden_signals.latency` - Boolean for latency metrics
    * `.observability.metrics.golden_signals.traffic` - Boolean for traffic/request metrics
    * `.observability.metrics.golden_signals.errors` - Boolean for error rate metrics
    * `.observability.metrics.golden_signals.saturation` - Boolean for resource saturation metrics
    * `.observability.summary.golden_signals_complete` - Boolean for all four signals monitored
  * Policy: Assert that all four golden signals are monitored
  * Configuration: None
  * Strategy: Strategy 10 (External Vendor API Integration)

* `metrics-latency-histogram` **Request latency histogram is tracked**: Services must track request latency using histograms for percentile calculations.
  * Collector(s): Query monitoring system or analyze metrics configuration for histogram metrics
  * Component JSON:
    * `.observability.metrics.has_latency_histogram` - Boolean for histogram presence
    * `.observability.metrics.latency_histogram_name` - Name of latency histogram metric
    * `.observability.metrics.latency_buckets` - Configured histogram buckets
  * Policy: Assert that request latency histogram is configured
  * Configuration: Required histogram bucket ranges
  * Strategy: Strategy 10 (External Vendor API Integration)

* `metrics-error-rate` **Error rate metrics are tracked**: Services must track error rates for reliability monitoring.
  * Collector(s): Query monitoring system or analyze metrics configuration for error metrics
  * Component JSON:
    * `.observability.metrics.has_error_rate` - Boolean for error rate metrics
    * `.observability.metrics.error_metric_name` - Name of error rate metric
  * Policy: Assert that error rate metrics are tracked
  * Configuration: None
  * Strategy: Strategy 10 (External Vendor API Integration)

* `metrics-resource-utilization` **Resource utilization metrics are exposed**: Services should expose resource utilization metrics (CPU, memory, connections).
  * Collector(s): Query monitoring system for resource metrics, or check for standard runtime metrics
  * Component JSON:
    * `.observability.metrics.has_resource_metrics` - Boolean for resource metrics
    * `.observability.metrics.resource_metrics` - Array of resource metric names
  * Policy: Assert that resource utilization metrics are exposed
  * Configuration: Required resource metrics (default: ["cpu", "memory", "connections"])
  * Strategy: Strategy 10 (External Vendor API Integration)

* `metrics-business` **Business metrics are tracked**: Services should track business-relevant metrics beyond technical health.
  * Collector(s): Query monitoring system for custom business metrics, or analyze metrics configuration
  * Component JSON:
    * `.observability.metrics.has_business_metrics` - Boolean for business metrics
    * `.observability.metrics.business_metrics` - Array of business metric names
  * Policy: Assert that business metrics are defined for production services
  * Configuration: Tags requiring business metrics, minimum business metric count
  * Strategy: Strategy 10 (External Vendor API Integration)

### Dashboards

* `metrics-dashboard-exists` **Service dashboard exists**: Every production service must have an operational dashboard for monitoring.
  * Collector(s): Check catalog annotations for dashboard link, or query monitoring system API (Grafana, Datadog) for dashboard existence
  * Component JSON:
    * `.observability.dashboard.exists` - Boolean for dashboard presence
    * `.observability.dashboard.url` - Dashboard URL
    * `.observability.dashboard.source` - Dashboard system (grafana, datadog, newrelic)
  * Policy: Assert that service dashboard exists
  * Configuration: Dashboard system to check, expected dashboard naming pattern
  * Strategy: Strategy 10 (External Vendor API Integration)

* `metrics-dashboard-linked` **Dashboard is linked from service catalog**: The dashboard URL should be registered in the service catalog for easy access.
  * Collector(s): Parse catalog annotations for dashboard link
  * Component JSON:
    * `.catalog.annotations.grafana_dashboard` - Grafana dashboard URL from catalog
    * `.catalog.annotations.datadog_dashboard` - Datadog dashboard URL from catalog
    * `.catalog.annotations.dashboard_linked` - Boolean for any dashboard annotation
  * Policy: Assert that dashboard is linked in service catalog
  * Configuration: Expected annotation keys
  * Strategy: Strategy 10 (External Vendor API Integration)

* `metrics-dashboard-golden-signals` **Dashboard includes golden signals**: Service dashboards should visualize all four golden signals.
  * Collector(s): Query dashboard API to analyze dashboard panels and metrics
  * Component JSON:
    * `.observability.dashboard.panels` - Array of dashboard panel definitions
    * `.observability.dashboard.has_golden_signals` - Boolean for golden signal coverage
    * `.observability.dashboard.missing_signals` - Array of missing golden signals
  * Policy: Assert that dashboard includes all golden signals
  * Configuration: None
  * Strategy: Strategy 10 (External Vendor API Integration)

* `metrics-dashboard-slo` **Dashboard includes SLO progress**: Dashboards should show SLO status and error budget consumption.
  * Collector(s): Query dashboard API to check for SLO-related panels
  * Component JSON:
    * `.observability.dashboard.has_slo_panels` - Boolean for SLO panels
    * `.observability.dashboard.has_error_budget_panel` - Boolean for error budget visualization
  * Policy: Assert that dashboard includes SLO information for services with defined SLOs
  * Configuration: None
  * Strategy: Strategy 10 (External Vendor API Integration)

---

## Observability - Distributed Tracing

### Tracing Configuration

* `tracing-configured` **Distributed tracing is configured**: Services must have distributed tracing instrumented for request flow visibility.
  * Collector(s): Check application configuration for tracing setup (OpenTelemetry, Jaeger, Zipkin), or verify tracing library dependencies
  * Component JSON:
    * `.observability.tracing.configured` - Boolean for tracing configuration
    * `.observability.tracing.library` - Tracing library used (opentelemetry, jaeger-client, zipkin)
    * `.observability.tracing.exporter` - Trace exporter destination
  * Policy: Assert that distributed tracing is configured
  * Configuration: Acceptable tracing libraries
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `tracing-opentelemetry` **Tracing uses OpenTelemetry standard**: Services should use OpenTelemetry for vendor-neutral tracing instrumentation.
  * Collector(s): Check dependencies for OpenTelemetry SDK, or analyze tracing configuration
  * Component JSON:
    * `.observability.tracing.uses_opentelemetry` - Boolean for OpenTelemetry usage
    * `.observability.tracing.library` - Tracing library used
  * Policy: Assert that OpenTelemetry is used for tracing
  * Configuration: Whether OpenTelemetry is required or just preferred
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `tracing-sampling-rate` **Trace sampling rate is appropriate**: Trace sampling should balance visibility with cost and performance.
  * Collector(s): Parse tracing configuration for sampling settings
  * Component JSON:
    * `.observability.tracing.sampling_rate` - Configured sampling rate (0.0-1.0)
    * `.observability.tracing.sampling_type` - Sampling strategy (probabilistic, rate-limiting, adaptive)
  * Policy: Assert that sampling rate is within acceptable bounds
  * Configuration: Min/max sampling rate (default: 0.01-1.0)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `tracing-required-attributes` **Traces include required attributes**: Traces should include standard attributes for consistent analysis.
  * Collector(s): Analyze tracing configuration for resource attributes
  * Component JSON:
    * `.observability.tracing.resource_attributes` - Array of configured resource attributes
    * `.observability.tracing.has_required_attributes` - Boolean for required attributes presence
  * Policy: Assert that traces include required attributes
  * Configuration: Required trace attributes (default: ["service.name", "service.version", "deployment.environment"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `tracing-context-propagation` **Trace context is propagated**: Services must propagate trace context to downstream services for end-to-end tracing.
  * Collector(s): Check tracing configuration for context propagation settings
  * Component JSON:
    * `.observability.tracing.context_propagation` - Boolean for context propagation enabled
    * `.observability.tracing.propagation_format` - Propagation format (w3c, b3, jaeger)
  * Policy: Assert that trace context propagation is configured
  * Configuration: Required propagation format (default: "w3c")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Health Checks & Probes

### Health Endpoint Configuration

* `health-endpoint-exists` **Health check endpoint exists**: Services must expose a health check endpoint for orchestrator and load balancer probes.
  * Collector(s): Parse application configuration for health endpoint, or probe common health paths in CI
  * Component JSON:
    * `.observability.health.endpoint_exists` - Boolean for health endpoint presence
    * `.observability.health.endpoint_path` - Health endpoint path (e.g., /health, /healthz)
  * Policy: Assert that health check endpoint is configured
  * Configuration: Expected health endpoint paths (default: ["/health", "/healthz", "/ready"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 15 (Runtime and Deployed State Verification)

* `health-endpoint-accurate` **Health check endpoint reflects true service health**: Health checks should verify actual service functionality, not just process liveness.
  * Collector(s): Analyze health endpoint implementation or configuration for dependency checks
  * Component JSON:
    * `.observability.health.checks_dependencies` - Boolean for dependency health checks
    * `.observability.health.dependencies_checked` - Array of dependencies verified in health check
    * `.observability.health.is_deep_health_check` - Boolean for comprehensive health check
  * Policy: Assert that health check verifies critical dependencies
  * Configuration: Required dependency types to check (default: ["database", "cache"])
  * Strategy: Strategy 15 (Runtime and Deployed State Verification)

* `health-probes-distinct` **Liveness and readiness probes are distinct**: Services should have separate liveness (is process alive) and readiness (can accept traffic) probes.
  * Collector(s): Parse Kubernetes manifests for probe configurations, or check application for separate endpoints
  * Component JSON:
    * `.observability.health.has_liveness_endpoint` - Boolean for liveness endpoint
    * `.observability.health.has_readiness_endpoint` - Boolean for readiness endpoint
    * `.observability.health.probes_are_distinct` - Boolean for distinct probe endpoints
  * Policy: Assert that liveness and readiness probes are configured separately
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `health-readiness-checks-deps` **Readiness probe checks dependency availability**: Readiness probes should verify that critical dependencies are accessible.
  * Collector(s): Analyze readiness probe endpoint implementation or configuration
  * Component JSON:
    * `.observability.health.readiness_checks_dependencies` - Boolean for dependency verification
    * `.observability.health.readiness_dependencies` - Array of dependencies checked
  * Policy: Assert that readiness probe verifies dependencies
  * Configuration: Required dependencies for readiness check
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `health-response-time-monitored` **Health check response time is monitored**: Health check latency should be monitored to detect degradation.
  * Collector(s): Query monitoring system for health check latency metrics
  * Component JSON:
    * `.observability.health.latency_monitored` - Boolean for latency monitoring
    * `.observability.health.latency_metric_name` - Name of health check latency metric
  * Policy: Assert that health check latency is tracked
  * Configuration: None
  * Strategy: Strategy 10 (External Vendor API Integration)

---

## Alerting

### Alert Configuration

* `alerting-configured` **Alerts are configured for the service**: Production services must have alerts configured for key failure scenarios.
  * Collector(s): Query monitoring system API for alerts/monitors associated with the service
  * Component JSON:
    * `.observability.alerts.configured` - Boolean for alert configuration
    * `.observability.alerts.count` - Number of alerts configured
    * `.observability.alerts.list` - Array of configured alert definitions
  * Policy: Assert that alerts are configured for production services
  * Configuration: Minimum number of alerts (default: 3)
  * Strategy: Strategy 10 (External Vendor API Integration)

* `alerting-routes-oncall` **Critical alerts route to on-call**: High-severity alerts must route to the on-call responder via incident management integration.
  * Collector(s): Query monitoring system for alert routing configuration, verify integration with PagerDuty/OpsGenie
  * Component JSON:
    * `.observability.alerts.critical_to_oncall` - Boolean for critical alert routing
    * `.observability.alerts.oncall_integration` - Incident management integration details
  * Policy: Assert that critical alerts route to on-call
  * Configuration: Alert severity levels requiring on-call routing
  * Strategy: Strategy 10 (External Vendor API Integration)

* `alerting-runbook-links` **Alerts include runbook links**: Alert definitions should include links to relevant runbook sections for responders.
  * Collector(s): Query monitoring system for alert annotations/descriptions
  * Component JSON:
    * `.observability.alerts.have_runbook_links` - Boolean for runbook links in alerts
    * `.observability.alerts.alerts_without_runbooks` - Array of alerts missing runbook links
  * Policy: Assert that alerts include runbook links
  * Configuration: Required runbook link format
  * Strategy: Strategy 10 (External Vendor API Integration)

* `alerting-slo-based` **SLO-based alerts are configured**: Services should have alerts triggered by SLO error budget consumption.
  * Collector(s): Query monitoring system for SLO burn rate or error budget alerts
  * Component JSON:
    * `.observability.alerts.has_slo_alerts` - Boolean for SLO-based alerts
    * `.observability.alerts.slo_burn_rate_alerts` - Array of burn rate alert definitions
  * Policy: Assert that SLO-based alerts are configured for services with defined SLOs
  * Configuration: Required burn rate thresholds (default: [2%, 5%, 10% per hour])
  * Strategy: Strategy 10 (External Vendor API Integration)

* `alerting-thresholds-tuned` **Alert thresholds are tuned appropriately**: Alert thresholds should be based on historical data and SLOs to minimize false positives.
  * Collector(s): Query monitoring system for alert trigger history and false positive rates
  * Component JSON:
    * `.observability.alerts.false_positive_rate` - False positive rate percentage
    * `.observability.alerts.alert_fatigue_risk` - Boolean for high alert volume
  * Policy: Assert that alert false positive rate is below threshold
  * Configuration: Maximum false positive rate (default: 10%)
  * Strategy: Strategy 10 (External Vendor API Integration)

* `alerting-severity-levels` **Alerts have appropriate severity levels**: Alerts should be classified by severity to enable appropriate response.
  * Collector(s): Query monitoring system for alert severity configurations
  * Component JSON:
    * `.observability.alerts.by_severity` - Count of alerts by severity level
    * `.observability.alerts.has_severity_classification` - Boolean for severity on all alerts
  * Policy: Assert that all alerts have severity classification
  * Configuration: Required severity levels (default: ["critical", "warning", "info"])
  * Strategy: Strategy 10 (External Vendor API Integration)

### Alert Fatigue Prevention

* `alerting-volume-manageable` **Alert volume is manageable**: The number of alerts should not overwhelm on-call responders.
  * Collector(s): Query incident management system for alert/incident volume over time
  * Component JSON:
    * `.oncall.alert_volume.weekly_alerts` - Average weekly alert count
    * `.oncall.alert_volume.daily_alerts` - Average daily alert count
    * `.oncall.alert_volume.is_excessive` - Boolean for excessive alert volume
  * Policy: Assert that alert volume is below fatigue threshold
  * Configuration: Maximum weekly alerts (default: 50)
  * Strategy: Strategy 10 (External Vendor API Integration)

* `alerting-deduplicated` **Alerts are deduplicated**: Multiple related alerts should be deduplicated to reduce noise.
  * Collector(s): Check monitoring/incident system configuration for deduplication rules
  * Component JSON:
    * `.observability.alerts.deduplication_configured` - Boolean for deduplication setup
    * `.observability.alerts.deduplication_rules` - Array of deduplication rules
  * Policy: Assert that alert deduplication is configured
  * Configuration: None
  * Strategy: Strategy 10 (External Vendor API Integration)

* `alerting-grouped` **Alert grouping is configured**: Related alerts should be grouped into incidents to reduce cognitive load.
  * Collector(s): Check incident management system for alert grouping/correlation rules
  * Component JSON:
    * `.observability.alerts.grouping_configured` - Boolean for alert grouping
    * `.observability.alerts.grouping_rules` - Array of grouping rules
  * Policy: Assert that alert grouping is configured
  * Configuration: None
  * Strategy: Strategy 10 (External Vendor API Integration)

---

## Disaster Recovery & Resilience

### Disaster Recovery Plan

* `dr-plan-exists` **Disaster recovery plan is documented**: Services must have a documented disaster recovery plan.
  * Collector(s): Check for DR plan in standard locations (e.g., `docs/dr-plan.md`), parse YAML frontmatter for recovery objectives and review metadata
  * Component JSON:
    * `.oncall.disaster_recovery.plan.exists` - Boolean for DR plan presence
    * `.oncall.disaster_recovery.plan.path` - Path to DR plan document
    * `.oncall.disaster_recovery.plan.sections` - Section headings found in the plan
  * Policy: Assert that DR plan exists for production services
  * Configuration: Candidate plan file paths
  * Strategy: Strategy 9 (Manual Process Documentation Verification)

* `dr-plan-rto-rpo-defined` **Recovery objectives (RTO/RPO) are defined**: The DR plan must define Recovery Time Objective and Recovery Point Objective.
  * Collector(s): Parse DR plan frontmatter for `rto_minutes` and `rpo_minutes`
  * Component JSON:
    * `.oncall.disaster_recovery.plan.rto_defined` - Boolean for RTO definition
    * `.oncall.disaster_recovery.plan.rto_minutes` - RTO in minutes
    * `.oncall.disaster_recovery.plan.rpo_defined` - Boolean for RPO definition
    * `.oncall.disaster_recovery.plan.rpo_minutes` - RPO in minutes
  * Policy: Assert that both RTO and RPO are defined
  * Configuration: Tags requiring RTO/RPO definition
  * Strategy: Strategy 9 (Manual Process Documentation Verification)

* `dr-plan-required-sections` **DR plan contains required sections**: The DR plan must include standard sections covering recovery procedures.
  * Collector(s): Parse DR plan markdown and extract section headings
  * Component JSON:
    * `.oncall.disaster_recovery.plan.sections` - Array of section headings found
  * Policy: Assert that all required sections are present (case-insensitive)
  * Configuration: Required section names (default: "Overview,Recovery Steps,Contact List")
  * Strategy: Strategy 9 (Manual Process Documentation Verification)

* `dr-plan-reviewed` **DR plan was reviewed recently**: Disaster recovery plans must be reviewed and updated periodically.
  * Collector(s): Parse DR plan frontmatter for `last_reviewed` date
  * Component JSON:
    * `.oncall.disaster_recovery.plan.last_reviewed` - ISO 8601 date of last review
    * `.oncall.disaster_recovery.plan.approver` - Email of the plan approver
  * Policy: Assert that plan was reviewed within threshold (compute freshness at evaluation time from `last_reviewed` date)
  * Configuration: Maximum days since review (default: 180)
  * Strategy: Strategy 9 (Manual Process Documentation Verification)

### DR Exercise Records

Exercises are stored as date-prefixed Markdown files in a directory (e.g., `docs/dr-exercises/2025-11-15.md`, `docs/dr-exercises/2025-05-20-database-failover.md`). The collector scans the directory, extracts metadata from each file, and provides the full exercise history.

* `dr-exercise-recent` **DR exercise was conducted recently**: Teams must conduct DR exercises (tabletop, failover, or full) within the configured threshold.
  * Collector(s): Scan exercise directory for date-prefixed `.md` files, parse frontmatter for `exercise_type`, extract section headings
  * Component JSON:
    * `.oncall.disaster_recovery.exercises[]` - Array of exercise records (date, path, exercise_type, sections)
    * `.oncall.disaster_recovery.latest_exercise_date` - Date of most recent exercise
    * `.oncall.disaster_recovery.exercise_count` - Total number of exercise records
  * Policy: Assert that most recent exercise is within threshold (compute freshness at evaluation time from `latest_exercise_date`)
  * Configuration: Maximum days since exercise (default: 365)
  * Strategy: Strategy 9 (Manual Process Documentation Verification)

* `dr-exercise-required-sections` **DR exercise records contain required sections**: Exercise records must include standard sections documenting the scenario and outcomes.
  * Collector(s): Parse exercise markdown and extract section headings
  * Component JSON:
    * `.oncall.disaster_recovery.exercises[].sections` - Array of section headings per exercise
  * Policy: Assert that required sections are present in latest exercise (or all exercises, configurable)
  * Configuration: Required section names (default: "Scenario,Recovery Steps Tested,Participants"), check all exercises or latest only (default: latest)
  * Strategy: Strategy 9 (Manual Process Documentation Verification)

### Resilience Patterns

* `resilience-circuit-breaker` **Circuit breaker is implemented for external calls**: Services should implement circuit breakers for calls to external dependencies.
  * Collector(s): Check dependencies for circuit breaker libraries, or analyze configuration for circuit breaker setup
  * Component JSON:
    * `.observability.resilience.circuit_breaker_configured` - Boolean for circuit breaker
    * `.observability.resilience.circuit_breaker_library` - Library used (hystrix, resilience4j, polly)
    * `.observability.resilience.protected_dependencies` - Array of dependencies with circuit breakers
  * Policy: Assert that circuit breakers are configured for services with external dependencies
  * Configuration: Required circuit breaker library per language
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `resilience-retry-backoff` **Retry logic with backoff is implemented**: Services should implement retries with exponential backoff for transient failures.
  * Collector(s): Check code or configuration for retry patterns
  * Component JSON:
    * `.observability.resilience.retry_configured` - Boolean for retry logic
    * `.observability.resilience.uses_exponential_backoff` - Boolean for backoff pattern
  * Policy: Assert that retry logic is configured for services with external calls
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `resilience-timeouts-configured` **Timeouts are configured for external calls**: All external service calls must have appropriate timeouts configured.
  * Collector(s): Check application configuration for timeout settings
  * Component JSON:
    * `.observability.resilience.timeouts_configured` - Boolean for timeout configuration
    * `.observability.resilience.default_timeout_ms` - Default timeout value
  * Policy: Assert that timeouts are configured for external calls
  * Configuration: Maximum allowed timeout (default: 30000ms)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `resilience-graceful-degradation` **Graceful degradation is implemented**: Services should degrade gracefully when dependencies are unavailable.
  * Collector(s): Check for fallback configurations or degradation documentation
  * Component JSON:
    * `.observability.resilience.graceful_degradation` - Boolean for degradation support
    * `.observability.resilience.fallback_behaviors` - Array of documented fallback behaviors
  * Policy: Assert that graceful degradation is documented for critical services
  * Configuration: Tags requiring graceful degradation
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Capacity Planning

### Load Projections

* `capacity-requirements-documented` **Capacity requirements are documented**: Services should have documented capacity requirements and scaling factors.
  * Collector(s): Check for capacity documentation in standard locations
  * Component JSON:
    * `.oncall.capacity.requirements_documented` - Boolean for capacity documentation
    * `.oncall.capacity.documentation_path` - Path to capacity documentation
  * Policy: Assert that capacity requirements are documented for production services
  * Configuration: Expected documentation locations
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `capacity-traffic-projections` **Traffic projections are maintained**: Services should have traffic projections for capacity planning.
  * Collector(s): Check for traffic projection documentation or capacity planning artifacts
  * Component JSON:
    * `.oncall.capacity.projections_documented` - Boolean for projection documentation
    * `.oncall.capacity.projected_growth_percentage` - Projected traffic growth percentage
  * Policy: Assert that traffic projections are documented
  * Configuration: Tags requiring traffic projections
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `capacity-scaling-thresholds` **Scaling thresholds are defined**: Auto-scaling configurations should have appropriate thresholds based on capacity planning.
  * Collector(s): Parse HPA or auto-scaling configurations for threshold values
  * Component JSON:
    * `.oncall.capacity.scaling_thresholds_defined` - Boolean for threshold definition
    * `.oncall.capacity.scale_up_threshold` - CPU/memory threshold for scaling up
    * `.oncall.capacity.scale_down_threshold` - Threshold for scaling down
  * Policy: Assert that scaling thresholds are explicitly defined
  * Configuration: Required threshold types (cpu, memory, custom metrics)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Resource Monitoring

* `capacity-utilization-monitored` **Resource utilization is monitored**: Services must have resource utilization monitoring for capacity planning.
  * Collector(s): Query monitoring system for resource utilization metrics and dashboards
  * Component JSON:
    * `.oncall.capacity.utilization_monitored` - Boolean for utilization monitoring
    * `.oncall.capacity.utilization_metrics` - Array of monitored resource types
  * Policy: Assert that resource utilization is monitored
  * Configuration: Required resource types (default: ["cpu", "memory", "disk", "network"])
  * Strategy: Strategy 10 (External Vendor API Integration)

* `capacity-utilization-alerts` **Resource utilization alerts are configured**: Alerts should fire when resource utilization approaches capacity limits.
  * Collector(s): Query monitoring system for resource-based alerts
  * Component JSON:
    * `.oncall.capacity.utilization_alerts_configured` - Boolean for utilization alerts
    * `.oncall.capacity.alert_thresholds` - Configured alert thresholds
  * Policy: Assert that resource utilization alerts are configured
  * Configuration: Required alert thresholds (default: 70%, 85%, 95%)
  * Strategy: Strategy 10 (External Vendor API Integration)

---

## Anomaly Detection

### Anomaly Detection Configuration

* `anomaly-detection-configured` **Anomaly detection is configured for key metrics**: Services should have anomaly detection enabled for critical metrics.
  * Collector(s): Query monitoring system for anomaly detection configurations (Datadog anomaly monitors, Prometheus anomaly detection rules)
  * Component JSON:
    * `.observability.anomaly_detection.configured` - Boolean for anomaly detection setup
    * `.observability.anomaly_detection.metrics_monitored` - Array of metrics with anomaly detection
    * `.observability.anomaly_detection.tool` - Anomaly detection tool used
  * Policy: Assert that anomaly detection is configured for production services
  * Configuration: Required metrics for anomaly detection (default: ["latency", "error_rate", "traffic"])
  * Strategy: Strategy 10 (External Vendor API Integration)

* `anomaly-baseline-established` **Baseline metrics are established**: Anomaly detection requires established baselines for comparison.
  * Collector(s): Query monitoring system for baseline/historical data availability
  * Component JSON:
    * `.observability.anomaly_detection.baseline_established` - Boolean for baseline data
    * `.observability.anomaly_detection.baseline_duration_days` - Duration of baseline data
  * Policy: Assert that metrics have sufficient baseline data for anomaly detection
  * Configuration: Minimum baseline duration (default: 14 days)
  * Strategy: Strategy 10 (External Vendor API Integration)

* `anomaly-deployment-detection` **Deployment anomaly detection is enabled**: Services should have detection for deployment-related anomalies.
  * Collector(s): Check for deployment markers in monitoring and associated anomaly detection
  * Component JSON:
    * `.observability.anomaly_detection.deployment_markers` - Boolean for deployment event markers
    * `.observability.anomaly_detection.deployment_anomaly_detection` - Boolean for deployment-specific detection
  * Policy: Assert that deployment anomaly detection is configured
  * Configuration: None
  * Strategy: Strategy 10 (External Vendor API Integration)

---

## Code-Level Operational Patterns (AST-Based)

These guardrails use Strategy 16 (AST-Based Code Pattern Extraction) to verify operational readiness patterns are implemented in code.

### Metrics Implementation

* `ops-metrics-declared` **Prometheus metrics are declared in code**: Services must declare Prometheus metrics (counters, gauges, histograms) for monitoring.
  * Collector(s): Use ast-grep to extract `prometheus.NewCounter()`, `prometheus.NewGauge()`, `prometheus.NewHistogram()` declarations
  * Component JSON:
    * `.code_patterns.metrics.declared` - Array of declared metrics with name, type, file, line
    * `.code_patterns.metrics.count` - Number of metrics declared
    * `.code_patterns.metrics.has_metrics` - Boolean indicating metrics are declared
  * Policy: Assert that at least minimum metrics are declared for service components
  * Configuration: Minimum metric count (default: 3)
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `ops-metrics-naming-convention` **Metrics follow naming conventions**: Declared metrics must follow Prometheus naming conventions (snake_case, appropriate suffixes).
  * Collector(s): Use ast-grep to extract metric names and validate against naming rules
  * Component JSON:
    * `.code_patterns.metrics.naming_violations` - Array of metrics with naming issues
    * `.code_patterns.metrics.follows_conventions` - Boolean for naming compliance
  * Policy: Assert that all metrics follow naming conventions
  * Configuration: Naming convention rules (suffix requirements for counters, histograms)
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `ops-metrics-have-labels` **Metrics have appropriate labels**: Metrics should have consistent labels for filtering and aggregation.
  * Collector(s): Use ast-grep to extract metric label definitions
  * Component JSON:
    * `.code_patterns.metrics.labels_used` - Array of label names across metrics
    * `.code_patterns.metrics.has_required_labels` - Boolean for required labels present
  * Policy: Assert that required labels are present on metrics
  * Configuration: Required labels (e.g., ["service", "environment"])
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Tracing Implementation

* `ops-tracing-spans-created` **Tracing spans are created for key operations**: Code must create tracing spans for important operations.
  * Collector(s): Use ast-grep to detect `tracer.Start()`, `otel.Tracer().Start()`, `span.Start()` patterns
  * Component JSON:
    * `.code_patterns.tracing.spans_created.count` - Number of span creation points
    * `.code_patterns.tracing.spans_created.locations` - Array of file/line locations
    * `.code_patterns.tracing.has_tracing` - Boolean indicating tracing is implemented
  * Policy: Assert that tracing spans are created in service code
  * Configuration: Minimum span creation points
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `ops-tracing-context-propagated` **Tracing context is extracted and injected**: Code must propagate tracing context across service boundaries.
  * Collector(s): Use ast-grep to detect `otel.GetTextMapPropagator().Extract()` and `Inject()` patterns
  * Component JSON:
    * `.code_patterns.tracing.propagation.extract_count` - Number of context extractions
    * `.code_patterns.tracing.propagation.inject_count` - Number of context injections
    * `.code_patterns.tracing.propagates_context` - Boolean for context propagation
  * Policy: Assert that tracing context is propagated in HTTP/gRPC handlers and clients
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Graceful Shutdown

* `ops-sigterm-handling` **SIGTERM signal is handled for graceful shutdown**: Services must handle SIGTERM for graceful shutdown in containerized environments.
  * Collector(s): Use ast-grep to detect `signal.Notify($$$, syscall.SIGTERM)` or equivalent patterns
  * Component JSON:
    * `.code_patterns.lifecycle.sigterm_handled` - Boolean for SIGTERM handling
    * `.code_patterns.lifecycle.signal_handling.location` - File/line of signal handling
  * Policy: Assert that SIGTERM is handled for service components
  * Configuration: Tags requiring signal handling (default: ["service", "backend"])
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `ops-graceful-shutdown-implemented` **Graceful shutdown drains connections**: Services must implement connection draining and cleanup on shutdown.
  * Collector(s): Use ast-grep to detect `server.Shutdown()`, drain patterns, or cleanup in signal handlers
  * Component JSON:
    * `.code_patterns.lifecycle.graceful_shutdown` - Boolean for graceful shutdown implementation
    * `.code_patterns.lifecycle.shutdown_pattern` - Type of shutdown pattern detected
  * Policy: Assert that graceful shutdown is implemented
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Feature Flags

* `ops-feature-flags-inventoried` **Feature flags are collected for inventory**: Feature flag usages should be extracted for tracking and lifecycle management.
  * Collector(s): Use ast-grep to detect feature flag library calls (LaunchDarkly, Unleash, custom patterns)
  * Component JSON:
    * `.code_patterns.feature_flags.flags` - Array of flag keys with file/line locations
    * `.code_patterns.feature_flags.count` - Number of distinct feature flags
    * `.code_patterns.feature_flags.library` - Feature flag library detected
  * Policy: Collect feature flag inventory (informational, not enforcement)
  * Configuration: Feature flag library patterns to detect
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `ops-feature-flags-naming` **Feature flags follow naming conventions**: Feature flag keys must follow organizational naming conventions.
  * Collector(s): Use ast-grep to extract flag keys and validate naming
  * Component JSON:
    * `.code_patterns.feature_flags.naming_violations` - Array of flags with naming issues
    * `.code_patterns.feature_flags.follows_conventions` - Boolean for naming compliance
  * Policy: Assert that all feature flags follow naming conventions
  * Configuration: Naming convention pattern (e.g., kebab-case, prefix requirements)
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Health Check Implementation

* `ops-health-endpoint-implemented` **Health check endpoint is implemented in code**: Service code must implement a health check handler.
  * Collector(s): Use ast-grep to detect health endpoint handler patterns (e.g., routes for /health, /healthz)
  * Component JSON:
    * `.code_patterns.health.endpoint_implemented` - Boolean for health endpoint in code
    * `.code_patterns.health.endpoint_path` - Detected health endpoint path
    * `.code_patterns.health.handler_location` - File/line of health handler
  * Policy: Assert that health endpoint handler exists in code
  * Configuration: Health endpoint patterns to detect
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `ops-health-checks-dependencies` **Health check verifies dependencies**: Health check implementation should verify critical dependencies.
  * Collector(s): Use ast-grep to analyze health handler for database ping, cache check, or dependency verification patterns
  * Component JSON:
    * `.code_patterns.health.checks_database` - Boolean for database check in health
    * `.code_patterns.health.checks_cache` - Boolean for cache check in health
    * `.code_patterns.health.dependency_checks` - Array of dependencies verified
  * Policy: Assert that health check verifies critical dependencies
  * Configuration: Required dependency checks
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Configuration Patterns

* `ops-env-vars-documented` **Environment variables are collected from code**: Environment variable usages should be extracted for documentation.
  * Collector(s): Use ast-grep to detect `os.Getenv()`, `env.Get()`, `process.env.` patterns
  * Component JSON:
    * `.code_patterns.config.env_vars` - Array of environment variable names with file/line
    * `.code_patterns.config.env_var_count` - Number of distinct environment variables
  * Policy: Collect environment variable inventory (informational)
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `ops-config-has-defaults` **Configuration values have defaults**: Configuration retrieval should include default values for optional settings.
  * Collector(s): Use ast-grep to detect `os.Getenv($KEY)` without fallback vs `getEnvOrDefault($KEY, $DEFAULT)` patterns
  * Component JSON:
    * `.code_patterns.config.missing_defaults.count` - Number of config reads without defaults
    * `.code_patterns.config.missing_defaults.locations` - Array of file/line locations
  * Policy: Assert that configuration values have appropriate defaults (may be advisory)
  * Configuration: Required vs optional config patterns
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

---

## Summary Policies

* `summary-oncall-ready` **On-call readiness is complete**: Aggregate check that all on-call requirements are met.
  * Collector(s): Aggregate on-call configuration checks
  * Component JSON:
    * `.oncall.summary.has_oncall` - On-call schedule exists
    * `.oncall.summary.has_escalation` - Escalation policy exists
    * `.oncall.summary.has_runbook` - Runbook exists
    * `.oncall.summary.has_sla` - SLA is defined
    * `.oncall.summary.oncall_ready` - Boolean for aggregate on-call readiness
  * Policy: Assert that aggregate on-call readiness is achieved
  * Configuration: Which on-call components are required
  * Strategy: other strategy (meta-policy aggregating other checks)

* `summary-observability-complete` **Observability is complete**: Aggregate check that all observability requirements are met.
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
  * Strategy: other strategy (meta-policy aggregating other checks)

* `summary-resilience-adequate` **Resilience posture is adequate**: Aggregate check that resilience patterns are implemented.
  * Collector(s): Aggregate resilience configuration checks
  * Component JSON:
    * `.observability.resilience.has_circuit_breakers` - Circuit breakers configured
    * `.observability.resilience.has_timeouts` - Timeouts configured
    * `.observability.resilience.has_retries` - Retry logic configured
    * `.observability.resilience.resilience_score` - Numeric resilience score
  * Policy: Assert that resilience score meets threshold
  * Configuration: Minimum resilience score, required resilience patterns per tier
  * Strategy: other strategy (meta-policy aggregating other checks)
