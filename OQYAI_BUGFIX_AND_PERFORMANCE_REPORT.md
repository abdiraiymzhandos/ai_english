# OqyAI bug fixes and performance report

Implementation: 2026-11-12. Independent verification and completion: 2026-11-13. Scope: this Django repository only. No deployment, production migration, fixture import, real outbound message, paid AI request, or Flutter change was performed. The initial Git working tree was clean. The local database was inspected read-only; mutations and migrations were exercised only in disposable test databases.

## Executive summary

Progress, vocabulary selection, retakes, loading feedback, cache isolation, and targeted performance improvements are implemented. The complete suite passes **74 tests on isolated MySQL 8.0.46**. SQLite discovers 74 tests: **69 pass and five real-row-lock tests are explicitly skipped**. The optional Chromium suite passes **11 checks**; the Node service-worker suite passes **3 checks**.

**The exact reported production `49/50` account could not be reproduced from the supplied local database.** It contains all Beginner IDs 1–50, one account with 50 permanent Beginner passes, and no account with exactly 49. A synthetic 49-pass learner correctly becomes `50/50 — 100%` after lesson 50, including before the patch. Therefore a simple final-boundary off-by-one was not the demonstrated cause of that particular account report. Confirmed progress defects and stale-cache behavior were fixed; the affected production record still needs the read-only diagnostic below. No completion was fabricated.

Current behavior is defined in [quiz contracts](docs/REALTIME_AND_QUIZ_CONTRACTS.md); this report records implementation evidence and limitations.

## Status of the four original problems

| Problem | Verified status | Remaining evidence needed |
| --- | --- | --- |
| Beginner progress | Fixed completion/access separation, boundaries, legacy scores, valid-answer reconciliation, and permanent completion through retakes. Synthetic 50th-lesson completion displays 100%. | The reported production 49/50 account remains unidentified/unverified. Local data was rechecked on November 13 and still has zero 49-pass accounts. |
| Quiz vocabulary | Current lesson pairs, distractors, stale-content rejection, user/track isolation, and cache isolation pass regressions on SQLite and MySQL. | Production authored content audit; local lesson 159 still needs translation/content correction. |
| Retake | Fresh run, saved prior completion, duplicate/delayed-answer handling, five-second timer, and three-mistake restart verified in backend/browser tests. | Physical-device and production-account smoke tests. |
| Loading/performance | Shared layout integration, links/forms/async recovery, back navigation, mobile viewport, and reduced motion verified. Dashboard SQL count remains seven versus 18 originally. | Production latency/CDN measurements and native Safari/WebView testing. |

## Additional fixes from the independent review

- A newly failing regression showed that a complete valid answer set was not reconciled when `completed=True` but `is_passed=False`. `start_quiz` now repairs either inconsistent flag **only from complete valid answer evidence**. This state is not present in the supplied local DB and is not claimed to explain the reported production account.
- Two browser regressions reproduced shared-loader lifecycle bugs: overlapping operations on the same button could restore an incorrect disabled/busy state, and a separate form watchdog survived back-navigation restoration. `loading.js` now counts active button operations and owns form cleanup through a single cancellable navigation watchdog.
- Quiz correct/incorrect feedback styles could be overridden by a later base button selector. More specific rules and computed-style browser assertions verify both feedback colors.
- Actual MySQL testing exposed two existing WhatsApp tests failing on four-byte emoji because the Django 5.1 connection default was `utf8`. The MySQL branch of `english_course/settings.py` now explicitly uses `utf8mb4`; a vocabulary round-trip regression and the complete MySQL suite pass. **This does not convert existing database/table/column charsets.** Check their compatibility before release.
- Migration backfill now reads explicit 500-row primary-key pages, so MySQL's buffered driver does not materialize the entire attempt table. Forward/backward rehearsal now includes 503 attempts across the batch boundary, preserving original completion/scores/answers and assigning distinct run UUIDs.
- Five concurrent MySQL tests verify simultaneous starts for different users, duplicate answers, duplicate final answers, restart racing a delayed answer, and duplicate third mistakes. No production service or database was contacted. The disposable server used `--no-defaults`, a fresh temporary datadir, a private Unix socket, and `--skip-networking`; it was stopped and removed afterward.
- Review of Kazakh/Russian gap handling found no further track-boundary defect beyond the already-fixed successor lookup; no speculative access-policy change was made.


## Discovery and reproduced root causes

Read `AGENTS.md`, the root context/map/router documentation, then `docs/INDEX.md` and relevant architecture, data-flow, content, quiz, testing, performance, environment, UX, and backlog sections. Source code and local aggregates were checked against the July documentation; several older descriptions no longer matched current runtime configuration.

| Finding | Exact original implementation and evidence | Implemented correction |
| --- | --- | --- |
| Wrong or unstable progress | `lessons/views.py::lesson_list` treated the guest session's **unlocked** IDs as completed IDs, wrote that list on every GET, filtered genuine passes according to paid access, and built levels by queryset row offsets. Repeated guest dashboard views fabricated progress; removing an ID moved lesson 51 into Beginner; unpaid status hid recorded completions. | `lessons/services/course_progress.py` uses permanent database passes, fixed ID boundaries, independent access decisions, and one narrow curriculum query. Dashboard GETs do not write sessions. Next existing lessons remain accessible across ID gaps. |
| Legacy score loss | `_quiz_state_payload` called `_sync_attempt_from_answers`, overwriting a passed attempt's saved score with zero when historical answer rows did not exist. Local data has **213 aggregate-only passed attempts**. | Preserve historical pass/score evidence. Never manufacture answer rows. Complete current answer evidence may repair a missing pass on quiz start; incomplete or absent evidence cannot. |
| Cross-track continuation | `_unlock_after_quiz_pass` selected the next ID without a track boundary, allowing Kazakh lesson 250 to lead into Russian lesson 251. | Track-bounded successor lookup; a final lesson completes even without a successor. Profile advancement uses a conditional update and never moves backwards. |
| Unrelated vocabulary | `generate_quiz_questions` stopped whenever any stored question existed. `start_quiz` served all stored questions attached to that lesson, even after its vocabulary changed. The local DB has **43 stale rows**: lesson 35: 14; 43: 9; 44: 10; 45: 10. | `lessons/services/quiz.py::vocabulary_pairs`, `prepare_questions`, and `bind_questions` select exact current lesson vocabulary pairs, add missing pairs, canonicalize duplicates, and fingerprint the run. Historical question rows remain stored but are not served. |
| Stale/cross-user cached quiz state | `static/sw.js` cached every successful same-origin GET, including `/start-quiz/<id>/` and personalized pages, under URL-only keys. It ignored privacy/cache-control semantics. This is confirmed code behavior; installation/activation on the affected production device is unknown. | Only content-hashed public static assets can be worker-cached. Activation deletes old OqyAI caches. Quiz APIs and learning pages return `no-store`; worker updates are revalidated. |
| Broken retake | `lesson_detail.html::showQuizComplete` offered `location.reload()`. `start_quiz` immediately returned the old pass; `submit_answer` refused passed attempts. | Explicit CSRF-protected restart POST and fresh run UUID. Permanent completion is separate from current-run completion. Previous successful score remains visible; failed retakes cannot revoke progress or access. |
| Lost-response UI freeze | The inline quiz client returned early on `already_answered`/`already_passed`, leaving disabled controls and no timer. Failed submissions also stopped the timer without an explicit recovery workflow. | `static/js/quiz.js` retries the exact answer/token, consumes authoritative duplicate state, advances correctly, and resumes after stale-state conflicts. Server writes remain idempotent. |
| Missing loading feedback | Standalone templates had no shared navigation/form lifecycle; fetch paths lacked consistent deadlines and duplicate guards. | Shared `loading.html`, `loading.js`, and `loading.css`; subtle nonblocking top bar, button busy states, accessible status, deadlines, errors, and history cleanup. |

Six new regressions failed against the original code: guest progress, legacy score preservation, level gaps, entitlement-independent completion, stale vocabulary, and track-end continuation. They now pass. The vocabulary bug was reproduced without borrowing production user data.

Distractors are inspected separately: choices contain distinct translations from the current lesson and exactly one copy of the correct translation. If translations repeat, fewer choices are preferable to invented placeholders or unrelated vocabulary. Run tokens, question IDs, lesson ownership, content hashes, and current pair membership are checked on submission. No shared per-user quiz cache or session question array is introduced.

## Implementation and changed files

Backend:

- `english_course/settings.py`: explicitly select `utf8mb4` for MySQL connections; SQLite and all existing table schemas remain unchanged.
- `lessons/services/course_progress.py`: shared completion, level/track boundaries, successor and existing access policy.
- `lessons/services/quiz.py`: vocabulary validation, exact-pair question synchronization, run binding/reset, authoritative answer serialization, and distractors.
- `lessons/models.py`: UUID, question-ID snapshot, vocabulary hash, previous successful score/total. Existing uniqueness constraints remain.
- `lessons/migrations/0017_quiz_run_state.py`: additive fields, individual UUID backfill, preserved legacy successful score; no completion/answer invention or question deletion.
- `lessons/views.py`: progress/detail integration, protected quiz endpoints, monotonic progression, completion-evidence recovery, uncached responses, and worker serving/revalidation.
- `lessons/urls.py`: `restart-quiz/<lesson_id>/` POST route.
- `lessons/middleware.py`: reuse the freshly loaded profile within the same request; device-count/lock policy is unchanged.
- `lessons/management/commands/audit_learning_data.py`: read-only vocabulary and optional account-progress diagnosis.

Frontend:

- `static/js/quiz.js`: isolated state machine, reset/resume/retake, exact-payload retry, five-second timer, score/mistakes, keyboard focus, next-lesson CTA, and history restoration.
- `static/js/loading.js`, `static/css/loading.css`, `lessons/templates/lessons/includes/loading.html`: reusable loading lifecycle without patching global fetch or browser history. Fast requests do not display a spinner; significant navigation responds immediately.
- `lessons/templates/lessons/lesson_detail.html`: external quiz module, saved score/retake UI, accessible errors, locally styled touch controls, deferred SweetAlert, audio `preload="none"`, voice script only for entitled users, and bounded explanation/chat requests. Updated dynamic AI output uses text nodes.
- `lessons/templates/lessons/lesson_list.html`: shared loader and bounded motivation/lead requests, duplicate lead guard, safe text rendering.
- Loader include only in `lessons/templates/lessons/account_locked.html`, `lessons/templates/lessons/advertisement.html`, `lessons/templates/lessons/auth_base.html`, `lessons/templates/lessons/base.html`, `lessons/templates/lessons/classroom/session.html`, `lessons/templates/lessons/privacy_policy.html`, and `lessons/templates/lessons/vocabulary_list.html`. Pages extending `auth_base.html` inherit it automatically.
- `static/sw.js`: cache isolation and old-cache removal. External payment links, downloads, Realtime requests, media, and personalized pages are not cached by this worker.

Tests and documentation:

- `lessons/test_learning_flow.py`, `lessons/test_quiz_migration.py`, `lessons/test_quiz_concurrency.py`, `lessons/browser_checks.py`, `lessons/js_tests/service-worker.test.cjs`: regressions, query/latency harness, migration rehearsal, real MySQL race tests, optional browser checks, and cache tests.
- `lessons/test_quiz_integrity.py`: token-aware requests; two stale Realtime assertions now use the existing shared model constant. No runtime AI model/prompt changed.
- `docs/ARCHITECTURE_AND_CODEBASE.md`, `docs/BACKLOG.md`, `docs/CONTENT_OPERATIONS.md`, `docs/ENVIRONMENT_AND_OPERATIONS.md`, `docs/INDEX.md`, `docs/REALTIME_AND_QUIZ_CONTRACTS.md`, `docs/TECHNICAL_AUDIT.md`, `docs/TESTING_AND_QUALITY.md`, and `docs/UX_UI_AUDIT.md`: current contracts/status/evidence. Backlog updates explicitly mark broader work as partial.
- This report: `OQYAI_BUGFIX_AND_PERFORMANCE_REPORT.md`.

## Performance measurements — original baseline and November 12 implementation

Method: existing Python 3.10.12 / Django 5.1.6 environment; disposable SQLite test DB; 300 synthetic lessons with four vocabulary pairs each; warm authenticated Django test client with middleware; ten measured requests per route after warm-up. No external services. Measurements include view/template/middleware execution, not network transport or rendering on a phone. SQL counts include transaction statements recorded by Django.

| Operation | Baseline SQL count | Final SQL count | Baseline median ms | Final median ms |
| --- | ---: | ---: | ---: | ---: |
| Dashboard | 18 | 7 | 36.105 | 42.406 |
| Lesson | 8 | 8 | 9.321 | 10.133 |
| Quiz start/resume | 14 | 12 | 11.865 | 10.949 |
| Duplicate answer/retry | 17 | 12 | 14.938 | 12.298 |
| Premium paywall | 5 | 5 | 7.110 | 6.890 |

**Query reductions are confirmed; end-to-end wall time did not improve uniformly.** Dashboard timing varied roughly 27–42 ms across post-change samples, so the final 42.406 ms is retained rather than selecting a faster run. Added integrity/score checks have a cost. These small synthetic samples are not production SLOs or proof of mobile speed. Django's rounded per-query timings produced 0.000 seconds for most statements; no meaningful SQL execution-time improvement can be inferred at that resolution.

Detected and addressed work:

- Five full-field catalog slices became one bounded `id/title` query. Completion membership is set-based. Repeated session writes are removed.
- Middleware's existing profile query is reused by views. Lesson detail spends the saved query on displaying the previous quiz result.
- Repeated answer counts and unconditional score writes are removed; state derives from one bounded answer read. Existing attempts are locked/read once on start. Answers lock only the learner's attempt, avoiding serialization of every learner of the same lesson.
- SQLite `EXPLAIN` uses the lesson primary key for catalog bounds, the existing unique attempt index for user progress, and the existing answer FK index. No speculative index migration or shared authorization cache was added.
- Lesson sections and level expansion remain local DOM operations. Quiz question advancement, retry, retake, and three-mistake restart avoid page reloads. Opening a new lesson/paywall/dashboard remains normal browser navigation with immediate feedback.
- Answer feedback was reduced from an unconditional 800 ms wait to 180 ms (zero with reduced motion). Chromium measured three ordinary click-to-next-question transitions at **200.8, 201.3, and 202.8 ms** in one local run; a later UI run measured **200.8–206.3 ms**. These include local request latency plus feedback and exclude real mobile networks.
- Benchmark lesson HTML fell from 42,355 to **36,343 bytes**. At that measurement the reusable loader was 6,455 bytes JS + 790 bytes CSS; the quiz module is 7,820 bytes. These add three first-load static requests and can be browser-cached. The **48,872-byte** voice script is no longer loaded for learners without voice access. Audio no longer preloads eagerly. External CDN sizes/availability and production compression were not measured.

Reproduce via `OQYAI_BENCHMARK=1 ... manage.py test lessons.test_learning_flow.CoursePerformanceTests`. Query budgets are asserted; wall-clock thresholds are intentionally not asserted on a shared machine.

## Performance recheck — November 13

The same ten-request synthetic SQLite harness was rerun after the independent fixes. Dashboard SQL stayed at **7** (originally 18), quiz start at **12** (originally 14), and duplicate-answer handling at **12** (originally 17).

| Operation | SQL queries | Median local response ms |
| --- | ---: | ---: |
| Dashboard | 7 | 28.753 |
| Lesson | 8 | 10.032 |
| Quiz start/resume | 12 | 10.174 |
| Answer retry | 12 | 13.301 |
| Paywall | 5 | 5.921 |

The final browser run measured ordinary quiz transitions at **201.5, 202.9, and 204.9 ms**. The current loader is 7,086 bytes JS plus 790 bytes CSS; quiz JS is 7,820 bytes; sample lesson HTML is 36,375 bytes. The loader grew slightly to fix overlapping-operation and watchdog cleanup. These are measured local values, not a mobile/production latency guarantee. SQL timer precision remains insufficient for a meaningful sub-millisecond SQL execution-time comparison.

## Testing and verification

The initial evidence below is retained as history. Final November 13 re-verification:

| Verification | Result |
| --- | --- |
| Full Django suite, SQLite / Django 5.1.6 | 74 discovered; **69 passed, 5 skipped** (row locks unsupported); 25.155 s |
| Full Django suite, MySQL 8.0.46 / mysqlclient 2.1.1 / Django 5.1.6 | **74 passed, no skips**, 33.116 s |
| Migration 0017, SQLite and MySQL | Forward and reverse rehearsal passed with 503 synthetic legacy attempts; original answers and completion retained |
| Concurrent MySQL quiz writes | All five race tests passed; separate thread connections and real row locks |
| Chromium 157.0.8103.78 | **11 passed**, 68.916 s; mobile/desktop, keyboard, timeouts, replay, history, loader overlap/watchdog cleanup; final feedback-style check included |
| Node worker checks | **3 passed** |
| Django check, migration drift, compilation, JS syntax, rendered inline JS, diff whitespace | Passed |

The first resumed MySQL full-suite run reproduced the new inconsistent-flag regression plus two emoji persistence errors. The fixes above resolved all three. The first two new loader tests also failed before their fixes and passed afterward. No failures were hidden by changing expected scoring/access behavior.

Historical November 12 runs:

1. Original full Django suite: 40 tests, 38 passed and two stale hard-coded Realtime-model assertions failed. Current runtime configuration was preserved; assertions were corrected to use `REALTIME_MODEL`.
2. Original new regression suite: six reproducible failures, now passing.
3. Final full Django suite: **67 passed**, 21.666 seconds. After the final start-query optimization, the affected **26-test** learning suite passed; the final standalone benchmark also passed.
4. Chromium 157.0.8103.78: **9 browser checks passed**, 67.250 seconds. Includes a 390×844 device viewport, desktop/back navigation, keyboard activation/focus, successful and failed retakes, lost-response retries, five-second timeouts, chat error feedback, loading timeout/concurrency, native form guard, external/download/hash/modifier exclusions, and reduced motion. Two affected mobile/reduced-motion checks passed again after final control styling.
5. `node --test lessons/js_tests/service-worker.test.cjs`: **3 passed**.
6. Django system check, migration drift check, Python compilation, new JavaScript syntax, rendered lesson/catalog inline JavaScript parsing, and final diff whitespace review: passed.
7. `collectstatic` into a temporary directory: passed; normal source static files were verified. Existing collected `staticfiles/` was not overwritten.
8. Migration forward/backward rehearsal preserved legacy completion, saved scores, and answer rows; new UUIDs are distinct. This first rehearsal was SQLite only; the November 13 rehearsal also passed on MySQL with 503 records.
9. `pip check`: existing failure — `httpcore 1.0.7` requires `h11 <0.15, >=0.13`, but `h11 0.16.0` is installed. Dependencies were not modified.

Browser testing used existing system Selenium via `PYTHONPATH`, not a new application dependency. Initial harness runs exposed a stale-element wait and lazy-loader test assumption, which were corrected. One Chromium startup attempt failed before any application test ran; subsequent runs passed. External CDNs were blocked and AI was mocked: local control fallback styling was visually inspected, but this is not a full production-CDN visual or accessibility audit. No live payment, AI, voice, translator, WhatsApp, physical iOS Safari, Android WebView, or production load test was performed. Local MySQL verification does not substitute for those checks. Existing automated registration/payment/Realtime tests still pass.

## Remaining issues and read-only diagnosis

- To investigate the reported account on the intended database, an authorized operator can run:

  ```bash
  python manage.py audit_learning_data --user-id <internal-account-id> --track kk --level 1
  ```

  The command reports missing completion lesson IDs and missing curriculum IDs without changing data or printing the account identity. If one lesson truly lacks pass/answer evidence, completing other lessons does not prove it was completed. A valid full answer set can be reconciled when that quiz opens; otherwise the missing quiz must be completed or investigated against trusted production records. Do not set a pass just to make a percentage reach 100.

- `python manage.py audit_learning_data` identified malformed untranslated vocabulary in **local lesson 159**. It needs authored content correction. The new parser returns a controlled error rather than silently skipping entries. Production contents may differ.
- The production MySQL version/schema, real data volume, migration duration, traffic, proxy/CDN, and activation of the old worker remain unavailable. Local MySQL 8.0.46 migration and concurrency tests now pass; rehearsal against the actual production-equivalent schema/data volume is still required. Do not infer lock duration or compatibility with another MySQL/MariaDB version from the local result.
- Local migration history includes an unrelated applied `0014_freevocabularypack_freevocabularyitem_and_more` absent from tracked migrations. It was not removed or edited. Inspect actual production migration history before release.
- Curriculum still uses legacy numeric IDs; the Russian catalog is not newly exposed. `current_lesson` remains the existing global scalar. Full attempt history, versioned publishing, and proper per-track profile metadata remain future work.
- AI generation still runs synchronously on the server. Browser deadlines release the UI but do not guarantee cancellation of server-side work. Durable jobs and server deadlines need separate bounded implementation. Native form watchdogs release feedback after 30 seconds; they cannot prove a server operation was rolled back.
- The five-second timer remains browser-enforced. This change does not introduce timed accommodations or a server-side timing contract.
- PWA offline personalized pages are intentionally unavailable: stale account/quiz data is not an acceptable offline source. Public immutable assets can still be cached.

## Safe PythonAnywhere deployment instructions

**Nothing has been committed, pushed, or deployed.** These are operator steps for a reviewed release. Ready for manual deployment review does not mean production prerequisites have been satisfied.

### Pre-release review and backup

1. In the existing PythonAnywhere **Web** tab, verify the application's source path, selected virtualenv/Python version, and linked WSGI configuration. Use that same virtualenv for management commands. Preserve the existing web app and WSGI/environment setup; do not create a new Django project. The Web tab's Reload control applies code changes. [PythonAnywhere deployment guide](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/)
2. Confirm the intended production DB configuration without printing credentials: `USE_MYSQL`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_HOST`, and `MYSQL_PORT` must refer to the existing database. Check the installed Django/mysqlclient versions, server version, SQL mode, and existing table/column charsets. The new connection charset is `utf8mb4`; it does not alter old columns. Do not copy local `.env` or `db.sqlite3` to production.
3. Back up the actual MySQL database and preserve the backup securely. Use the exact database name from PythonAnywhere's Databases tab, including its `$`, in single quotes. Verify restoration into a **separate staging database**, never over production for a routine release. Example placeholders, to be adapted by the operator:

   ```bash
   mysqldump -u <account> -h <mysql-host> --set-gtid-purged=OFF --no-tablespaces --column-statistics=0 'account$database' > <secure-backup-path>
   ```

   PythonAnywhere documents the host/name lookup, quoting, backup options, and restoration. No backup or restore against production was executed here. [PythonAnywhere MySQL backup guide](https://help.pythonanywhere.com/pages/MySQLBackupRestore/)
4. Rehearse the reviewed release/migration against a staging copy with the production engine, schema, and representative attempt-table volume. Inspect the extra local-only migration history finding separately; do not use `--fake` to conceal schema differences.

### Apply the reviewed schema and static files

From the actual deployed repository, with the Web app's virtualenv activated and production environment loaded, the reviewed sequence is:

```bash
python manage.py check
python manage.py showmigrations lessons
python manage.py migrate --plan
python manage.py sqlmigrate lessons 0017
# Only after backup, staging rehearsal, and release approval:
python manage.py migrate lessons 0017
python manage.py collectstatic --noinput
```

`sqlmigrate` shows DDL but cannot display the Python UUID/score backfill. The new migration is additive, retains original completion/answer data, and backfills metadata in bounded pages. It was tested both directions on SQLite and local MySQL 8.0.46. **MySQL DDL is not transactionally rolled back on failure**; schema changes can still lock tables. Use a reviewed maintenance/write-quiescence window, avoid new quiz traffic during backfill, and stop for operator inspection if a DDL step fails. Do not repeatedly rerun or fake a partly applied migration. [Django MySQL migration limitations](https://docs.djangoproject.com/en/5.1/topics/migrations/#mysql)

In the PythonAnywhere Web tab, ensure `/static/` maps to this repository's configured absolute `STATIC_ROOT` (`.../english_course/staticfiles`), not the source `static/` folder. `collectstatic` must include `js/loading.js`, `js/quiz.js`, `css/loading.css`, and `sw.js`. Then use **Reload** for the existing web app. Test the asset URLs afterward. Keep `/sw.js` handled by the Django route so its revalidation/scope headers are present; do not add a broad mapping for private media. [PythonAnywhere Django static-file guide](https://help.pythonanywhere.com/pages/DjangoStaticFiles/)

No new application dependency or environment variable was added. Ensure the deployed virtualenv already has the supported MySQL driver. The existing dependency conflict requires a separate reviewed environment repair; do not silently upgrade production packages as part of this patch.

### Post-deployment checklist

- [ ] Confirm migration 0017 is applied and PythonAnywhere error logs show no import/schema/charset errors.
- [ ] Verify all new static asset URLs and `/sw.js` (new version, `Cache-Control: no-cache`, scope `/`). Confirm old OqyAI caches are removed after the worker updates/activates.
- [ ] Reload old open quiz tabs. A stale/missing run token must return controlled HTTP 409, not modify a new run.
- [ ] Run `audit_learning_data` read-only against the affected account; record exactly which Beginner lesson, if any, lacks completion evidence. Confirm 50 valid passes render 50/50 and 100%.
- [ ] Complete a synthetic/staging final Beginner quiz, open the next lesson, retake, fail a retake, and confirm saved completion/unlocks remain.
- [ ] Verify both tracks and paid/unpaid/teacher/guest access using authorized test accounts; no price or entitlement changes are expected.
- [ ] Verify quiz correct answers match the displayed lesson, five-second timeout, three-mistake reset, and retry after a lost response.
- [ ] Verify links/forms/AI-loading errors, history restoration, downloads/external payment links, and native Safari/Chrome/WebView behavior.
- [ ] Confirm `no-store` on learning pages/quiz APIs, four-byte Unicode persistence where needed, and current browser/server latency against the production baseline.
- [ ] Smoke-test existing auth, subscription/paywall, AI, voice, translator, and messaging integrations through the usual authorized process. These live integrations were not invoked during this task.

### Rollback considerations

Prefer a forward fix after identifying the fault. If rolling back application code, retain additive fields initially; permanent completion stays present, but the old retake/cache bugs return. Reversing migration 0017 was rehearsed and removes only added run/saved-result fields, retaining original completion/question/answer records; it loses new metadata and must be coordinated with matching application code. MySQL partial-DDL failures require schema inspection and a reviewed recovery plan. Never reset progress, overwrite the production DB with the local database, or restore an old backup over newer learner activity without an explicit recovery decision.

## Further improvements

Prioritize production request/SQL tracing and browser resource timings, then optimize measured bottlenecks. Candidate next steps: trim the large catalog DOM, consolidate inline CSS into fingerprinted assets, verify modern Django static storage/compression configuration, reduce external CDN dependencies, introduce durable bounded AI work, and benchmark device middleware under concurrent traffic. Keep authorization and quiz state out of shared page caches. Automate the now-executed MySQL race/migration checks in CI and add real-device coverage before claiming native WebView verification.

## Final review status

**Ready for manual deployment review**, with the documented staging/backup/schema/device checks required before release. All implemented learning regressions pass; local MySQL migration, rollback, Unicode, and concurrency checks pass. The production 49/50 account remains unresolved without its database evidence. The pre-existing dependency conflict and physical-device/live-integration checks remain visible limitations. Migration 0017 is intentionally still pending in the supplied local project database. No commit, push, deployment, or production-data change was performed.

## Markdown inventory at discovery

Root: `ADMIN_ACCESS_OPERATIONS.md`, `AGENTS.md`, `CLASSROOM_ARCHITECTURE.md`, `CLASSROOM_MVP_NOTES.md`, `ENVIRONMENT_DEPLOYMENT.md`, `FEATURES_MAP.md`, `FILE_MAP.md`, `FIXTURE_CONTENT_WORKFLOW.md`, `KNOWN_RISKS.md`, `PROJECT_CONTEXT.md`, `README.md`, `TASK_PLAYBOOK.md`, `VOICE_LESSON_README.md`, `WHATSAPP_AGENT_SETUP.md`.

`docs/`: `AI_AGENT_RUNBOOK.md`, `AI_INTEGRATIONS.md`, `ARCHITECTURE_AND_CODEBASE.md`, `ARCHITECTURE_AND_DATA_FLOW.md`, `BACKLOG.md`, `CONTENT_OPERATIONS.md`, `DOCUMENTATION_AUDIT.md`, `ENVIRONMENT_AND_OPERATIONS.md`, `FEATURE_ROADMAP.md`, `IMPLEMENTATION_PLAN.md`, `INDEX.md`, `REALTIME_AND_QUIZ_CONTRACTS.md`, `SECURITY_AUDIT.md`, `TECHNICAL_AUDIT.md`, `TESTING_AND_QUALITY.md`, `UX_UI_AUDIT.md`.
