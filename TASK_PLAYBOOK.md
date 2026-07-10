# Task playbook

This is a short routing document. Detailed implementation and operations guidance lives under `docs/`.

## Start every task

```bash
git status --short
git branch --show-current
git diff --stat
```

Record pre-existing changes and do not reformat or overwrite them. Read [AGENTS.md](AGENTS.md), then find the stable Task ID in [docs/BACKLOG.md](docs/BACKLOG.md). One Task ID should normally be one Codex session and one coherent review.

## Task sequence

1. Reproduce the finding with a failing test or safe diagnostic.
2. Confirm authorization, data, migration, deployment, and rollback impact.
3. Implement the smallest complete scope in the backlog acceptance criteria.
4. Run targeted tests, then the full configured suite when safe.
5. Perform the listed manual QA, including mobile/keyboard/error paths where relevant.
6. Update the source-of-truth documents listed in the task.
7. Review `git status`, `git diff --check`, `git diff --stat`, and the full diff.

## Routing

- Security/payment: [security audit](docs/SECURITY_AUDIT.md) → [implementation plan](docs/IMPLEMENTATION_PLAN.md)
- Architecture/database: [architecture map](docs/ARCHITECTURE_AND_CODEBASE.md) → [technical audit](docs/TECHNICAL_AUDIT.md)
- AI/voice/WhatsApp: [AI integrations](docs/AI_INTEGRATIONS.md) → [Realtime contracts](docs/REALTIME_AND_QUIZ_CONTRACTS.md)
- Content/fixtures: [content operations](docs/CONTENT_OPERATIONS.md)
- UX/features: [UX audit](docs/UX_UI_AUDIT.md) → [feature roadmap](docs/FEATURE_ROADMAP.md)
- Deployment/testing: [environment and operations](docs/ENVIRONMENT_AND_OPERATIONS.md) → [testing and quality](docs/TESTING_AND_QUALITY.md)

Do not deploy, migrate production data, rotate credentials, send external messages, rewrite Git history, or change commercial/consent rules without explicit authorization for that action.
