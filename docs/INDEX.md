# Documentation index

This index defines documentation ownership after the 2026-07-10 repository audit. Each fact should have one primary home; other documents link to it.

## Canonical documents

| Document | Audience and purpose | Source-of-truth responsibility | Related documents | Update trigger |
| --- | --- | --- | --- | --- |
| [README](../README.md) | Everyone; repository landing page | Short product and audit status only | [AGENTS](../AGENTS.md), [project context](../PROJECT_CONTEXT.md) | Major product/repository entry-point change |
| [AGENTS](../AGENTS.md) | Coding agents and engineers | Safety rules, task routing, invariants, definition of done | [Backlog](BACKLOG.md), [testing and quality](TESTING_AND_QUALITY.md) | Any workflow/invariant/document route change |
| [Project context](../PROJECT_CONTEXT.md) | New engineer/product collaborator | Five-to-ten-minute current product orientation | [Architecture and codebase](ARCHITECTURE_AND_CODEBASE.md), [feature roadmap](FEATURE_ROADMAP.md) | Role, flow, monetization, or product-state change |
| [Architecture and codebase](ARCHITECTURE_AND_CODEBASE.md) | Engineers | System/app boundaries, file map, data model, request flows | [Technical audit](TECHNICAL_AUDIT.md), [AI integrations](AI_INTEGRATIONS.md) | App/model/route/major service change |
| [AI integrations](AI_INTEGRATIONS.md) | AI/backend/security engineers | Model/prompt/transport/output/cost/privacy map | [Realtime and quiz contracts](REALTIME_AND_QUIZ_CONTRACTS.md), [security audit](SECURITY_AUDIT.md) | AI endpoint/model/prompt/provider change |
| [Realtime and quiz contracts](REALTIME_AND_QUIZ_CONTRACTS.md) | Implementers/testers | Protocol and quiz integrity contracts | [AI integrations](AI_INTEGRATIONS.md), [testing and quality](TESTING_AND_QUALITY.md) | Realtime event or quiz invariant change |
| [Content operations](CONTENT_OPERATIONS.md) | Content/admin/data engineers | Lesson/fixture/import/version/QA workflow | [Architecture and codebase](ARCHITECTURE_AND_CODEBASE.md), [testing and quality](TESTING_AND_QUALITY.md) | Lesson schema/import/export/admin change |
| [Security audit](SECURITY_AUDIT.md) | Security/engineering/product | Confirmed vulnerabilities, risks, validation | [Backlog](BACKLOG.md), [environment and operations](ENVIRONMENT_AND_OPERATIONS.md) | Finding fixed/accepted/new evidence |
| [Technical audit](TECHNICAL_AUDIT.md) | Engineering/architecture | Code/data/performance/debt findings | [Architecture and codebase](ARCHITECTURE_AND_CODEBASE.md), [backlog](BACKLOG.md) | Finding fixed/accepted/new evidence |
| [UX/UI audit](UX_UI_AUDIT.md) | Product/design/frontend | Journey, accessibility, conversion findings | [Feature roadmap](FEATURE_ROADMAP.md), [backlog](BACKLOG.md) | Flow/UI/accessibility or analytics change |
| [Feature roadmap](FEATURE_ROADMAP.md) | Product/engineering | Implemented inventory and proposed opportunities | [UX/UI audit](UX_UI_AUDIT.md), [implementation plan](IMPLEMENTATION_PLAN.md) | Feature scope/prioritization/evidence change |
| [Backlog](BACKLOG.md) | Product/engineering/agents | Stable executable Task IDs and acceptance criteria | [Implementation plan](IMPLEMENTATION_PLAN.md), [security audit](SECURITY_AUDIT.md), [technical audit](TECHNICAL_AUDIT.md) | Task status/scope/dependency changes |
| [Implementation plan](IMPLEMENTATION_PLAN.md) | Delivery/engineering | Ordered phases and release gates | [Backlog](BACKLOG.md), [environment and operations](ENVIRONMENT_AND_OPERATIONS.md) | Task order/status/operational constraint change |
| [Environment and operations](ENVIRONMENT_AND_OPERATIONS.md) | DevOps/operators/engineers | Configuration, deployment, media, backup, incident facts | [Security audit](SECURITY_AUDIT.md), [testing and quality](TESTING_AND_QUALITY.md) | Environment/dependency/deployment change |
| [Testing and quality](TESTING_AND_QUALITY.md) | Engineers/QA | Actual checks, coverage gaps, quality gates | [AGENTS](../AGENTS.md), [environment and operations](ENVIRONMENT_AND_OPERATIONS.md) | Test/tool/CI change or audit rerun |
| [Documentation audit](DOCUMENTATION_AUDIT.md) | Maintainers | Inventory, duplication, deprecation, update rules | [AGENTS](../AGENTS.md), [documentation index](INDEX.md) | Documentation architecture changes |

## Specialized operational documents

| Document | Status | Responsibility | Related documents |
| --- | --- | --- | --- |
| [Admin access operations](../ADMIN_ACCESS_OPERATIONS.md) | Current concise runbook | Existing access flags/admin behavior; canonical domain rules remain in architecture/backlog | [Architecture and codebase](ARCHITECTURE_AND_CODEBASE.md), [backlog](BACKLOG.md) |
| [Classroom architecture](../CLASSROOM_ARCHITECTURE.md) | Current specialized map; feature experimental | Classroom files/flows; security/privacy findings live in security/UX audits | [Security audit](SECURITY_AUDIT.md), [UX/UI audit](UX_UI_AUDIT.md) |
| [Classroom MVP notes](../CLASSROOM_MVP_NOTES.md) | Deprecated historical record | No current facts; link to replacements | [Classroom architecture](../CLASSROOM_ARCHITECTURE.md), [feature roadmap](FEATURE_ROADMAP.md) |
| [Environment deployment](../ENVIRONMENT_DEPLOYMENT.md) | Deprecated pointer | Replacement: environment and operations | [Environment and operations](ENVIRONMENT_AND_OPERATIONS.md) |
| [Features map](../FEATURES_MAP.md) | Deprecated pointer | Replacements: project context and feature roadmap | [Project context](../PROJECT_CONTEXT.md), [feature roadmap](FEATURE_ROADMAP.md) |
| [File map](../FILE_MAP.md) | Deprecated pointer | Replacement: architecture and codebase | [Architecture and codebase](ARCHITECTURE_AND_CODEBASE.md) |
| [Fixture workflow](../FIXTURE_CONTENT_WORKFLOW.md) | Deprecated pointer | Replacement: content operations | [Content operations](CONTENT_OPERATIONS.md) |
| [Known risks](../KNOWN_RISKS.md) | Deprecated pointer | Replacements: security/technical audits and backlog | [Security audit](SECURITY_AUDIT.md), [technical audit](TECHNICAL_AUDIT.md), [backlog](BACKLOG.md) |
| [Task playbook](../TASK_PLAYBOOK.md) | Current concise router | Task execution skeleton only | [AGENTS](../AGENTS.md), [backlog](BACKLOG.md) |
| [Voice lesson README](../VOICE_LESSON_README.md) | Deprecated pointer | Replacements: AI integrations and Realtime contracts | [AI integrations](AI_INTEGRATIONS.md), [Realtime and quiz contracts](REALTIME_AND_QUIZ_CONTRACTS.md) |
| [WhatsApp setup](../WHATSAPP_AGENT_SETUP.md) | Sanitized/deprecated | Environment names and safe verification only; never live identifiers | [AI integrations](AI_INTEGRATIONS.md), [environment and operations](ENVIRONMENT_AND_OPERATIONS.md) |
| [AI agent runbook](AI_AGENT_RUNBOOK.md) | Deprecated pointer | Replacements: AGENTS, task playbook, environment/testing docs | [AGENTS](../AGENTS.md), [task playbook](../TASK_PLAYBOOK.md), [testing and quality](TESTING_AND_QUALITY.md) |
| [Old architecture/data flow](ARCHITECTURE_AND_DATA_FLOW.md) | Deprecated pointer | Replacement: architecture and codebase | [Architecture and codebase](ARCHITECTURE_AND_CODEBASE.md) |

## Evidence conventions

- `Confirmed`: directly observed in tracked code, templates, migrations, tests, safe command output, or aggregate fixture analysis.
- `Inferred`: strongly suggested by evidence but not demonstrated at runtime.
- `Needs verification`: requires browser, credentials, production access, external service, or current data.
- `Needs product-owner confirmation`: a business/product rule is absent or contradictory.
- Confidence: `High`, `Medium`, or `Low`.

Do not put secret values, private identifiers, production data, or time-sensitive external-service state in documentation.
