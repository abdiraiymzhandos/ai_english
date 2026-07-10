# Documentation audit

Audit date: 2026-07-10. Scope: all 16 Markdown files that existed before this audit (2,880 lines), checked against tracked code, tests, migrations, configuration, templates, static assets, and safe aggregate fixture/runtime diagnostics.

Documentation must contain environment variable names and operational categories only—never credential values, private contacts, payment-recipient identifiers, customer data, PINs, or short-lived provider state.

## Original-document inventory and disposition

| Original path | Purpose | Accuracy at audit start | Problems found | Action taken/recommended | Current source of truth |
| --- | --- | --- | --- | --- | --- |
| `AGENTS.md` | Agent entry, invariants, commands | Strong baseline | Wrong local venv assumption; incomplete WhatsApp/test/privacy gates; duplicated deep detail | Rewritten as concise primary entry and task router | `AGENTS.md` |
| `PROJECT_CONTEXT.md` | Broad product/repository snapshot | Useful fragments | Dated, duplicative, contradictory classroom/voice/document status | Rewritten as five-to-ten-minute implemented/partial/experimental/missing product brief | `PROJECT_CONTEXT.md` |
| `FILE_MAP.md` | Path navigation | Mostly accurate | Stale classroom label, missing newer services, duplicated architecture | Marked deprecated; later archival candidate | `docs/ARCHITECTURE_AND_CODEBASE.md` |
| `FEATURES_MAP.md` | Feature-to-code map | Mostly accurate | Mixed implemented/planned, stale classroom and webhook claims | Marked deprecated; later archival candidate | `PROJECT_CONTEXT.md`, `docs/FEATURE_ROADMAP.md` |
| `KNOWN_RISKS.md` | Risk register | Materially stale | Claimed tests effectively absent despite 40 tests; stale WIP/voice state | Marked deprecated; later archival candidate | `docs/SECURITY_AUDIT.md`, `docs/TECHNICAL_AUDIT.md`, `docs/BACKLOG.md` |
| `TASK_PLAYBOOK.md` | Task checklists | Useful workflow | Duplicated maps/runbook and omitted WhatsApp threat workflow | Rewritten as short Task-ID execution router | `TASK_PLAYBOOK.md`, `AGENTS.md` |
| `ENVIRONMENT_DEPLOYMENT.md` | Settings/deploy facts | Partly accurate | No real dependency, backup, health, restore, private-media, release baseline | Marked deprecated pointer | `docs/ENVIRONMENT_AND_OPERATIONS.md` |
| `CLASSROOM_ARCHITECTURE.md` | Classroom code/flow | Routes/models mostly accurate | Incorrectly called tracked code uncommitted local WIP; privacy not central | Rewritten as current experimental architecture and blocker map | `CLASSROOM_ARCHITECTURE.md` |
| `CLASSROOM_MVP_NOTES.md` | Implementation diary/plans | Historical detail | 353-line mixed diary/current/planned record; incorrectly canonical | Marked deprecated; later archival after product-owner review | `CLASSROOM_ARCHITECTURE.md`, security/UX/feature docs |
| `VOICE_LESSON_README.md` | Realtime voice notes | Transport accurate | Duplicated contracts; other docs mislabeled it; current prompt wiring contradicted it | Marked deprecated pointer | `docs/AI_INTEGRATIONS.md`, `docs/REALTIME_AND_QUIZ_CONTRACTS.md` |
| `WHATSAPP_AGENT_SETUP.md` | Setup and operational state | Code-flow portions useful | Contained live-looking credential/identifiers/private payment/contact data; omitted signature/retention risks | Sanitized and deprecated; rotate exposed category; no live values in docs | `docs/AI_INTEGRATIONS.md`, security/environment docs |
| `FIXTURE_CONTENT_WORKFLOW.md` | Content/fixture guidance | Counts and contamination correctly noted | Did not make private snapshot removal/restore safety strong enough | Marked deprecated pointer | `docs/CONTENT_OPERATIONS.md` |
| `ADMIN_ACCESS_OPERATIONS.md` | Access/admin operator map | Helpers/actions mostly accurate | Called tracked classroom local WIP; treated booleans as operational truth without payment audit | Rewritten as concise current-state and safety runbook | This file plus architecture/backlog |
| `docs/AI_AGENT_RUNBOOK.md` | Git/test/deploy/rollback workflow | Useful baseline | Wrong venv location; rollback was not backup; duplicated task playbook | Marked deprecated pointer | `AGENTS.md`, `TASK_PLAYBOOK.md`, environment/testing docs |
| `docs/ARCHITECTURE_AND_DATA_FLOW.md` | System/data/request flow | Strong baseline | Omitted WhatsApp entities/Telegram flow/private-media risk | Marked deprecated pointer | `docs/ARCHITECTURE_AND_CODEBASE.md` |
| `docs/REALTIME_AND_QUIZ_CONTRACTS.md` | Realtime/quiz invariants | Quiz/TTS mostly accurate | Conflated browser remote audio with backend deltas; prompt claim contradicted worktree | Rewritten and retained as specialized contract | Same file |

No obsolete file was deleted. Deprecated files explain why and link to replacements.

## Current documentation architecture

| Layer | Documents | Responsibility |
| --- | --- | --- |
| Entry | `README.md`, `AGENTS.md`, `PROJECT_CONTEXT.md`, `TASK_PLAYBOOK.md` | Concise orientation, safety, product state, and task routing |
| Index/governance | `docs/INDEX.md`, this audit | Ownership, update triggers, evidence/deprecation rules |
| System/domain | `docs/ARCHITECTURE_AND_CODEBASE.md`, `docs/AI_INTEGRATIONS.md`, `docs/CONTENT_OPERATIONS.md`, `docs/REALTIME_AND_QUIZ_CONTRACTS.md`, `CLASSROOM_ARCHITECTURE.md` | Current implementation, interfaces, invariants, sensitive change maps |
| Audit | `docs/SECURITY_AUDIT.md`, `docs/TECHNICAL_AUDIT.md`, `docs/UX_UI_AUDIT.md` | Evidence-based findings, severity, consequences, remediation/validation |
| Product/delivery | `docs/FEATURE_ROADMAP.md`, `docs/BACKLOG.md`, `docs/IMPLEMENTATION_PLAN.md` | Opportunities, stable executable tasks, ordered phases |
| Engineering operations | `docs/ENVIRONMENT_AND_OPERATIONS.md`, `docs/TESTING_AND_QUALITY.md`, `ADMIN_ACCESS_OPERATIONS.md` | Build/deploy/backup/monitor/test/access procedures and gaps |

The complete purpose/audience/update-trigger table is [INDEX.md](INDEX.md).

## Duplication resolved

- Orientation/file/feature/risk facts formerly repeated across five root documents now have separate product, architecture, audit, and backlog owners.
- Task workflow formerly duplicated between `TASK_PLAYBOOK.md` and the AI runbook now lives in `AGENTS.md`/`TASK_PLAYBOOK.md` with environment/testing links.
- Classroom current code is in `CLASSROOM_ARCHITECTURE.md`; the old MVP diary is historical.
- Realtime transport is in the contracts; prompts/models/privacy/cost are in AI integrations; the voice README is a pointer.
- Deployment facts and procedures are unified in environment/operations; test evidence is separate.
- WhatsApp durable architecture/security replaces live setup state and identifiers.

## Archive candidates

After one release cycle and product-owner confirmation that no unique decision remains, move—not delete—these deprecated pointers/notes to an archive location:

- `CLASSROOM_MVP_NOTES.md`
- `FILE_MAP.md`
- `FEATURES_MAP.md`
- `KNOWN_RISKS.md`
- `ENVIRONMENT_DEPLOYMENT.md`
- `FIXTURE_CONTENT_WORKFLOW.md`
- `VOICE_LESSON_README.md`
- `docs/AI_AGENT_RUNBOOK.md`
- `docs/ARCHITECTURE_AND_DATA_FLOW.md`

Keep the sanitized WhatsApp warning pointer until credential rotation/history handling is complete.

## Update triggers

- App/model/route/service boundary → architecture/data map and affected contract.
- Model/migration/content import → architecture, content operations, backlog/plan, test evidence.
- AI provider/model/prompt/event/usage policy → AI integrations, contracts, security, tests.
- Auth/role/entitlement/payment → project context, architecture access matrix, security, UX, operator runbook.
- Template/flow/copy/accessibility → UX audit; feature roadmap only if opportunity scope changes.
- Dependency/runtime/settings/deploy/storage/worker → environment/operations, testing, AGENTS.
- Finding remediated/accepted → audit evidence and Task status/validation; do not erase history without a decision record.
- Feature implemented → move state from proposed to implemented with code/test evidence.

## Review rules

1. Code and executed evidence outrank old prose.
2. Separate current, experimental, proposed, and unverified states.
3. Use stable Task/Feature/UX/Security IDs; never renumber for convenience.
4. Put a fact in one canonical file and link elsewhere.
5. Use `Needs product-owner confirmation` for commercial/role/consent ambiguity.
6. Never claim browser/live production/external-service validation from static code.
7. Never copy private values while documenting a credential or data exposure.
8. Run the link/task-ID/sensitive-data checks in [TESTING_AND_QUALITY.md](TESTING_AND_QUALITY.md) after documentation changes.
