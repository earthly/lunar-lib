# Starter+ Packs

**Coming soon.**

Starter+ packs require light configuration — a secret (API key, token) or a URL to connect to an external service. Easy to set up but not zero-config.

## Planned Packs

Starter+ packs will cover vendor integrations and tools that need credentials:

- **Jira / Linear** — Ticket traceability (`JIRA_TOKEN`, `LINEAR_API_KEY`)
- **Snyk** — Enterprise SCA scanning (`SNYK_TOKEN`)
- **SonarQube** — Code quality gates (`SONAR_TOKEN`)
- **Codecov** — Coverage enforcement (`CODECOV_TOKEN`)
- **PagerDuty / OpsGenie** — On-call verification (`PAGERDUTY_API_KEY`)
- **Datadog / Grafana** — Observability dashboards (API keys)
- **Helm** — Helm chart validation (`helm` binary)
- **Dependabot / Renovate** — Dependency update tracking

Each pack will follow the same format as the [Starter](../starter/) packs — a `lunar-config.yml` with curated policies and enforcement levels.
