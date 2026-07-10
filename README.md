# OqyAI

OqyAI is a Django English-learning platform primarily for Kazakh-speaking learners. The repository currently contains a 250-lesson web catalog, quizzes and progress, AI explanations and Realtime voice features, a translator, an experimental classroom system, and a WhatsApp sales/receipt workflow.

Start with [AGENTS.md](AGENTS.md) for safe engineering rules and [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for a five-to-ten-minute product orientation. The documentation source-of-truth map is [docs/INDEX.md](docs/INDEX.md).

## Current audit status

The evidence-based audit was completed on 2026-07-10. It found critical payment-automation and security risks. The repository is **not documented as production-ready**. Before feature work, follow the execution order in [docs/BACKLOG.md](docs/BACKLOG.md) and [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).

Recommended first implementation task: `SEC-001` — Stop OCR-only automatic entitlement grants.

## Safe local orientation

From the Git root:

```bash
git status --short
python3 --version
python3 manage.py check
python3 manage.py test
```

In the audited workspace, the usable virtual environment was at `../venv`; do not assume that path exists elsewhere. Discover or create an environment according to [docs/ENVIRONMENT_AND_OPERATIONS.md](docs/ENVIRONMENT_AND_OPERATIONS.md). Never commit `.env`, databases, media, receipts, classroom photos, or user-data exports.
