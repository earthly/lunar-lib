Please arm yourself with as much context as possible about Lunar from @lunar-lib/ai-context/AGENTS.md , @lunar-lib/ai-context/about-lunar.md , @lunar-lib/ai-context/core-concepts.md and @lunar-lib/ai-context/component-json-structure.md .

Then, get inspired with ideas from @lunar-lib/ai-context/guardrails.md and the examples pasted below (from our website).

<examples>
📂 Repository and Ownership
Documentation: README standards, runbook location, required links
Ownership: CODEOWNERS validation, HRIS cross-reference
Settings: branch protection, merge requirements
Catalog: service registry integration (Backstage, etc)
Configuration: required dot files present and valid
🚀 Deployment and Infrastructure
Kubernetes: resource limits, non-root containers, min replicas
IaC: Terraform validation, WAF/DDOS config, tagging
CD pipelines: dry-run validation, approval gates
Security: encryption in transit and at rest
Lifecycle: no stale deployments, delete protection
🧪 Testing and Quality
Unit tests: coverage thresholds, framework standards
Integration tests: required for APIs, conventions enforced
Performance tests: load testing procedures, benchmarks
CI execution: tests run in pipeline and deployed version
Test quality: fast execution, no flaky tests
🏗️ DevEx, Build and CI
Golden paths: approved runtimes, frameworks, and templates
Dependencies: pinned versions, no EOL or restricted libraries
Images: approved base images and registries, proper labels
Artifacts: signed and published to approved locations
Build quality: reproducible builds, performance standards
🔒 Security and Compliance
Scanning: SAST, SCA, container and artifact scanning
Vulnerabilities: critical issues fixed within SLA
SBOM: software bill of materials generated and published
Secrets: no plaintext secrets, approved vault usage
Compliance: SOC 2, NIST/SSDF, PCI-DSS, ISO 27001
⚙️ Operational Readiness
Documentation: runbooks, SLA/SLO, incident dashboards
On-call: rotation configured, escalation paths, HRIS sync
Observability: structured logging, metrics, distributed tracing
Monitoring: golden signals, health checks, alerting
Resilience: DR procedures, backup validation, anomaly detection
</examples>

Then, please come up with a highly detailed list of possible policies for the first category: "Repository and Ownership". Aim for 30-50.

This list should be in Markdown, placed in the folder @guardrail-specs .

Use the following format:

```Markdown
* <Summary description>: <Detailed description>.
  * Collector(s): <description of what data the collector(s) need to get>
  * Component JSON:
    * `<path>` - what the path signifies
    * `<path>` - what the path signifies
    * ...
  * Policy: <description of what the policy checks>
  * Configuration: <exposed parameters that would change the behavior / threshold>
* ...
```

Don't use code. Use only high-level descriptions in English.