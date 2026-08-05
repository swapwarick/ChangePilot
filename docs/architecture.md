# Architecture

ChangePilot uses Clean Architecture boundaries:

- API routes convert HTTP requests into application commands.
- Application services coordinate analysis, graph construction, scoring, and reporting.
- Domain modules hold deterministic risk logic and provider interfaces.
- Infrastructure adapters call external services.

## Deterministic Risk Boundary

Risk scoring lives in `backend/app/risk`. It accepts only deterministic inputs and emits evidence-backed scores. AI providers are not imported by the risk package.

## AI Provider Boundary

AI providers implement `AIProvider` and are selected through `AIProviderRegistry`. Business logic asks the registry for a configured provider by task, not by vendor.

## Extension Interfaces

Future integrations should implement adapters without changing business logic:

- Git providers: GitHub, GitLab, Bitbucket, Azure DevOps.
- Work tracking: Jira, ServiceNow.
- Infrastructure: Kubernetes, Terraform, AWS, Azure, GCP.
- Observability: Prometheus, Grafana, Datadog.

