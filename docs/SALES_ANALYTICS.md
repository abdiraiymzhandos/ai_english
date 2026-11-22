# Course sales and product analytics

## Owner workflow

Open **Django Admin → OqyAI аналитикасы → Сатылым аналитикасы**, or `/admin/insights/visit/`. Staff need the **insights | Сатылым аналитикасы | Can view** permission (`insights.view_visit`). The default **Соңғы 7 күн (бүгінді қоса)** covers today and the six previous Asia/Almaty calendar dates, through report generation. On 22 November 2026 it selects 16–22 November. **Соңғы 7 толық күн** selects 15–21 November. Choose **Өзге аралық**, enter both dates and click **Есепті көрсету** for a custom inclusive range. The 14-day and 30-day presets each offer both an including-today and a complete-day version. Today, yesterday, this month and the previous month remain available.

**Кезеңдегі белсенділік** shows dated activity within the selected period, including returning learners. **Тіркелгендер тобы** selects accounts by actual registration date and follows their recorded activity through the report generation time. The dashboard prints the observation cutoff and freshest event. The date and mode select the population and the observation window. Activity mode includes accounts registered, active or confirmed in the range. Cohort mode includes only accounts registered in the range.

### Customer follow-up

The segment describes the customer **at report generation**. The rules use current course access, durable passed lessons and all retained purchase-intent events through generation, including events outside the selected window. Every included customer has one segment. Priority order for contacting prospects is HOT, WARM, COLD, then PAID.

| Segment | Evidence | Follow-up |
| --- | --- | --- |
| PAID — Ақылы клиент | Current paid course access takes precedence over all other evidence | Existing customer. Check independent confirmation separately |
| HOT — Ыстық клиент | Unpaid with a retained purchase click or WhatsApp redirect | High |
| WARM — Жылы клиент | Other unpaid customer with all three saved free passes on one track or a retained offer view | Medium |
| COLD — Суық клиент | Other unpaid customer, including a new registration | Low. Check coverage before drawing conclusions |

A learner can move from COLD at signup to WARM at the third saved pass, HOT at handoff and PAID when access is granted. Retention and opt-out can remove evidence. These operational categories do not estimate a purchase probability or reconstruct a historical account state.

Use the customer selector for any segment, no recorded lesson opening, opening without saved completion, one or two free passes, three passes while unpaid, three without an observed offer, offer without click, click without confirmed purchase, handoff while unpaid, or confirmed buyer. Sort by follow-up priority, last in-window activity, registration, saved completions, retained paywall views or retained clicks. Summary cards cover the entire selected population. Search, sort and customer filters apply to the list and the corresponding Users and User_Journeys rows. Journeys keep chronological order within each account. Overview, Funnel, Events and Sources retain the full selected population for consistent denominators.

| Access | Django permission in addition to admin staff status |
| --- | --- |
| Behavioral report and pseudonymous workbook | `insights.view_visit` |
| Current names, phones, partial contact search and manual contact | Also `insights.view_customer_contacts` |
| Include direct identifiers in workbook | Also `insights.export_customer_contacts` |
| Include internal accounts for debugging | Also `insights.include_internal_accounts` |
| Open a linked profile record | Standard lessons UserProfile view or change permission |

Superusers have these permissions. Search by numeric account ID or, with contact access, by partial username or formatted phone. Searches use a CSRF-protected form so contact queries stay out of navigation URLs. Select **Жолы** for the timeline and access/confirmation details. The profile, copy and WhatsApp controls use current registration details. Phones are unverified. Eligible local 11-digit numbers beginning with 7 or 8 produce a digits-only wa.me link. Opening it is manual and emits no learner event.

Standard reports exclude current staff, superusers and members of the explicit Django group **OqyAI Analytics Test**. Create the group and add synthetic accounts if needed. **Ішкі аккаунттарды қосу** enables an authorized diagnostic view. A linked visit identifies its anonymous events for exclusion. Other visits on the same browser remain eligible.

**Excel есебін жүктеу** produces one workbook. **Клиенттердің аты мен телефон нөмірін қосу** defaults off. Authorized opt-in adds current username, exact registered phone text and verification status in Users only. Each export records operator, mode, dates, event count, contact inclusion and internal inclusion in the admin log. Download responses are private/no-store.

| Sheet | Contents |
| --- | --- |
| Overview | Dates, local timezone, cutoff, freshness, activity and business KPIs |
| Funnel | Unique learners advancing in order, previous/initial conversion, drop-off and mean elapsed minutes |
| Users | Account IDs, optional identity, segment, priority, source, dated milestones, saved progress, observed attempts, page views, visit spans, CTA/offer/click/handoff counts and times, access, independent confirmation and coverage |
| User_Journeys | Dated, meaningful account events with page, visit, lesson, track and origin |
| Events | Detailed recorded events including anonymous activity and cleaned campaign fields |
| Sources | Unique learners and purchases by first recorded source and campaign |
| Definitions | Event names, denominator rules, missing values and historical caveats |

The XLSX writer uses a temporary file, streamed response and write-only worksheet output. Text is written as literal Excel strings. Date windows are limited to 731 days, with up to 10,000 accounts and 50,000 events per report. If exceeded, choose a narrower range. Default exports contain pseudonymous behavioral data. A contact-inclusive download contains personal information. The owner should review access, lawful collection, notice/consent, storage, retention and the intended external processor before sharing a workbook.

## Offer, access and confirmation

The standard annual course price is **15,000 KZT**. `COURSE_PRICE_KZT` in Django settings supplies the sales page, catalog guide, WhatsApp sales prompt, payment instructions and receipt amount check. Production environment settings, including the site's loaded .env, can override the default. Set `COURSE_PRICE_KZT=15000` in the active PythonAnywhere configuration for web and background processes. An existing 25000 override takes precedence. Voice, translator and other premium products have separate entitlements/offers. The annual offer uses the existing manual Kaspi/WhatsApp channel. The existing access flag has no expiry field.

An actual first quiz pass establishes permanent lesson completion. The offer uses this evidence and the access decision for lesson 4 or 254. It appears after answer feedback and remains available from the catalog or the boundary lesson. A learner who completes lesson 3 out of order sees a lesson success rather than a three-lesson claim. The existing Russian-track exception for authenticated unpaid non-teachers continues to apply. Opening an already passed quiz can recover progress from earlier answers without manufacturing a new dated completion.

Staff verify payment independently, select the unpaid profile under **User profiles**, then choose **Тексерілген курс төлемін растау және ақылы қолжетімділік беру**. This existing bulk activation action locks profiles and creates one dated first-purchase record per learner with the confirming staff ID. Repeating it creates no extra sale. Ordinary profile checkbox edits and existing automated receipt processing grant access under their existing rules and supply no verified sale to this report. A WhatsApp redirect records handoff intent. It cannot attest that WhatsApp launched, a message was sent, or money arrived. Confirmed revenue remains unknown because the system has no verified payment amount. Renewals, refunds and provider settlement are outside this ledger.

## Measurement

A deferred first-party script emits a single view for each displayed document and a fresh view on a real browser-history restore. The server accepts known routes, explicitly named client actions, bounded JSON and sanitized UTM slugs. No raw paths with query strings, referrer URLs, form input, quiz answers, usernames, phone numbers, headers or IPs enter event storage. Source links can use `/?utm_source=threads&utm_medium=social&utm_campaign=november`. Use non-personal marketing slugs only. Initial visitor attribution linked to an observed signup is used for acquisition, while event rows carry visit attribution. Missing signup evidence or attribution is `unknown`. A later tagged visit cannot establish the original acquisition source of a legacy account. An explicit direct campaign tag is distinguishable from unknown traffic.

| Event group | Events and evidence |
| --- | --- |
| Visits and accounts | `session_started` on creation of a visit, `page_view` from a displayed document, `signup_completed` from registration, `login_completed` and `logout_clicked` from successful auth transitions |
| Learning | `course_dashboard_opened` and `lesson_opened` derive from one accepted view. Opening and starting a lesson are indistinguishable. `quiz_started` is the first served attempt. `quiz_restarted`, `quiz_completed`, `quiz_failed`, first-pass `lesson_completed` and per-track `free_course_completed` come from the quiz transaction. |
| Interactions | `audio_play`, `audio_error`, `next_lesson_clicked`, `quiz_catalog_clicked`, `subscription_cta_viewed` and `subscription_cta_clicked` are client observations. Visibility observations require IntersectionObserver. |
| Sales | `paywall_viewed` derives from a displayed offer, `paywall_purchase_clicked` and `whatsapp_opened` from the CSRF-protected handoff POST, `purchase_completed` from the verified staff activation |
| Presence | `activity` is a throttled signal following interaction. A recent interaction may generate a final visibility/pagehide signal. |

One signed random HttpOnly cookie identifies the browser independently of the Django session credential. A 30-minute gap starts a new visit. Anonymous activity in the active visit can be associated with the signed-in account. Logout drops the visitor cookie. Visits and users have separate denominators. DNT, Global Privacy Control and `PRODUCT_ANALYTICS=0` suppress product-event collection. Business purchase confirmations remain available. Device categories rely on standalone mode or recognizable browser/WebView signals. Ambiguous clients remain unknown. Activity spans are estimates. They cannot establish an exact exit or a cause of abandonment.

The funnel counts distinct accounts passing each preceding stage in order, including first, second and third lessons on the same track. Activity mode starts with active accounts. Cohort mode starts with registrations. The KPI conversion cards count accounts exhibiting both events in time order divided by distinct accounts at the first milestone. A zero denominator is unknown. Source unknowns are retained. CRM filters use retained evidence and current saved progress. Dated funnel milestones and activity columns follow the reporting window. Current profile lesson and highest passed lessons per track come from the current profile and durable QuizAttempt.is_passed. These snapshots cannot establish the date of an old pass. Historical registration dates are available. Pre-instrumentation sessions, clicks, attribution, payment times and amounts cannot be reconstructed.

## Storage and operation

`insights.0001_initial` creates five tables. Visitor serializes identity and the cross-worker rate counter. Visit contains bounded attribution, platform and activity bounds. Event has a UUID primary key and indexed time, user and kind. PendingEvent is a small transactional outbox. Purchase stores verified first activations independently of raw retention. Core transactions only enqueue local rows. Workers materialize committed events under row locks and deduplicate by event UUID. Client ingestion requires CSRF, same origin, a signed visitor cookie, allowlisted actions and a v4 UUID. The database enforces 90 client submissions per visitor per minute. An additional short-lived, keyed, per-worker address bucket limits bursts. Raw IPs are not stored.

Page views drain a small batch of the visitor's pending rows. The admin drains up to 100 pending milestones before reporting and flags a remaining backlog. The Always-on worker periodically calls `process_analytics --limit 5000` for timely processing without traffic. Database outages can leave gaps in telemetry. A warning is logged on failed milestone enqueue. Learning progress and verified purchases have their own authoritative records.

Raw retention defaults to 180 days (`ANALYTICS_RETENTION_DAYS`). Preview with `python manage.py prune_analytics --dry-run`. Apply the approved policy with `python manage.py prune_analytics --apply`. The command removes expired pending and materialized events, expired visits and unreferenced visitor identities in batches. Purchase evidence and ordinary learning records have independent lifetimes. Backups and downloaded workbooks need a separate retention policy.

### Delivery diagnostics

The former ingestion handler turned every database exception into an undifferentiated HTTP 503. No exception evidence identifies the three original requests. Holding a simultaneous visitor write on disposable SQLite reproduced a 503, including on file-backed SQLite. An independent MySQL row-lock timeout produced the same result. Releasing the writer and replaying the original UUID twice produced one event. The handler logs vendor, category and exception class. SQLite busy/locked and MySQL lock timeout/deadlock are retryable. Other database errors produce 500 and require investigation.

The browser normally sends one request at a time with at most 24 queued events. Network failures and 502/503/504 responses get up to three exponential retries with jitter. Identity-bound headers and stable UUIDs survive retries. Changing the session or visitor invalidates the old document. Page exit clears queued retries and may dispatch one final queued navigation click. Closing a page, sustained outages, rate limits or an overflowing queue can still leave gaps. Learning and purchase actions run independently.

Audio observation covers native audio and nested source errors, an early capture listener and observable pre-existing error states. A section and bounded error code accompany each phase once per lesson section per document. Playback phase requires an observed play event. A control gesture that the browser never exposes cannot be distinguished from preload. The local missing media produced real preload and playback errors in Chromium. Error ordering does not establish why someone stopped learning.

The fresh browser check used `/?utm_source=threads&utm_medium=social&utm_campaign=test`, registered a synthetic account, opened a lesson and the paywall, submitted the purchase handoff and returned via a different campaign. Original signup and Sources retained threads/test. A new tagged visit carried the later campaign. Old untagged activity remains unknown. The existing marketing slug format excludes dotted values such as `chatgpt.com`. A website campaign cannot establish attribution after an App Store or Google Play installation without additional supported attribution.

### Registration alerts

Registration previously ran Telegram synchronously in an after-commit callback. Requests received a scalar timeout of 5 seconds for both connection and read inactivity. The account could already be saved while the browser waited for Telegram. Registration now inserts a unique per-user delivery job in its transaction. Enqueue failures roll back a savepoint and log the exception class. The Always-on worker handles Telegram asynchronously. No message payload is stored in analytics or the queue.

The worker commits a conditional claim before sending. Successful sends stay sent. Connect timeouts and explicit 429 responses can retry up to three attempts, after 5 and 25 minutes subject to the scheduler. Ambiguous read failures and other failures enter review. A worker crash can leave a sending claim. Inspect `RegistrationNotification` status and the destination before manually requeuing any ambiguous delivery. Avoid replaying sent jobs. To inspect counts without reading contact details:

```bash
python manage.py shell -c "from lessons.models import RegistrationNotification as J; from django.db.models import Count; print(list(J.objects.values('status').annotate(count=Count('pk'))))"
```

## Local owner review

From `~/english_platform/english_course`, apply the additive migrations to the intended development database when ready. The automated checks use disposable databases.

```bash
export USE_MYSQL=0
../venv/bin/python manage.py migrate --plan
../venv/bin/python manage.py migrate insights
../venv/bin/python manage.py migrate lessons
../venv/bin/python manage.py runserver
```

Open `/admin/insights/visit/` with the appropriate staff permissions. Choose **Бүгін** for a new account, or the date of the original signup in cohort mode. Compare a known learner's contact details, free passes, timeline and access against the admin profile. Search by part of the phone and apply HOT. Download with the contact option off and on, compare Users and User_Journeys, then check both export entries in the admin log. For new attribution evidence, enter the Threads URL in a fresh private window. Use a test account and stop at the WhatsApp redirect.

## PythonAnywhere release

Django, the admin report and Excel use the pinned Python IANA timezone database. `Asia/Almaty` preserves historical UTC+6 and uses UTC+5 for November 2026. Analytics converts local midnights to UTC instants before filtering indexed registration, event and purchase timestamps. Conversion to calendar dates and Excel clock times happens in Python. The workbook retains its seven sheets. Current CRM status and retained evidence continue to use their documented observation rules.

The repository command `python manage.py run_background_worker` serves both queues in one Always-on Task. Its default alert batch is 100 every 15 seconds and its analytics batch is 5,000 every 60 seconds. Each poll waits after its own batch and can start while the other is busy. Successful registration alerts keep the existing username, registered phone, role, WhatsApp and admin link format. The three deployed analytics and notification migrations are already applied. This maintenance release requires only the packaged timezone dependency and process restarts.

Follow the [single-task cutover, verification and rollback instructions](ENVIRONMENT_AND_OPERATIONS.md#timezone-and-worker-cutover). Keep retention pruning on its existing approved schedule.

## Timezone and worker verification

The maintenance suite passed 119 of 127 Django tests on SQLite, with eight MySQL-specific skips. All 127 passed on disposable MySQL. One Chromium check passed at 320, 390 and 1024 pixels with today's new learner in the default list. Workbook readback, fresh WSGI and management process startup, historical offsets, midnight boundaries, unchanged raw UTC storage, worker shutdown signals and the exact Telegram message were verified locally. Django system checks and migration drift checks passed. The local migration plan was empty.

## Previous CRM verification

The automated suites use synthetic users, mocked notification delivery, disposable databases and headless Chromium. Physical devices, production data, live Telegram/WhatsApp delivery and settlement require separate verification. The production migration and static collection commands above are operator steps.

The SQLite suite passed 111 of 119 tests, with eight MySQL-specific skips. Disposable MySQL passed all 119. The suites exercised a real writer lock, idempotent recovery, report permissions, both workbook variants and concurrent notification claims. Increasing the synthetic population by 1,000 users with profiles kept the report SQL query count constant. A separate file-backed SQLite lock rehearsal passed. All seven Node tests passed, including the service-worker and retry/queue checks. Django system checks and migration drift checks passed.

All 15 selected Chromium scenarios passed on a disposable file-backed SQLite database. They covered the mobile quiz and paywall, owner journey navigation, a clean Threads signup and later campaign, workbook source counts, actual media failures before and after playback intent, and duplicate media callbacks. Django checks, JavaScript syntax and whitespace checks passed.

The preceding funnel release also rehearsed applying, reversing and reapplying its initial migration on an isolated MySQL database with 1,100 synthetic accounts. Existing account, paid-profile and saved-pass counts survived that prior rehearsal.

## Files changed in the CRM update

| Directory | Files |
| --- | --- |
| `docs/` | `SALES_ANALYTICS.md` |
| `insights/` | `admin.py`, `crm.py`, `models.py`, `reports.py`, `taxonomy.py`, `tracking.py`, `views.py`, `workbook.py`, `test_crm.py`, `tests.py` |
| `insights/migrations/` | `0002_alter_visit_options_event_context.py` |
| `insights/templates/admin/insights/visit/` | `report.html` |
| `english_course/services/` | `telegram.py` |
| `lessons/` | `browser_checks.py`, `models.py`, `tests.py`, `views.py` |
| `lessons/services/` | `registration_notifications.py` |
| `lessons/management/commands/` | `process_registration_notifications.py` |
| `lessons/migrations/` | `0018_registrationnotification.py` |
| `lessons/js_tests/` | `product-analytics.test.cjs` |
| `lessons/templates/lessons/` | `lesson_detail.html`, `includes/loading.html` |
| `static/css/` | `funnel-admin.css` |
| `static/js/` | `analytics-admin.js`, `product-analytics.js` |
