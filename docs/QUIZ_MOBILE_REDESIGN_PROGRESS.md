# Mobile quiz redesign

## November 15 implementation record

**Status: implemented and locally verified; ready for manual review.** Frontend slice of UX-003/UX-004. The working tree was clean at start. No backend, schema, AI model, subscription, Flutter, production-data, commit, push, or deployment changes.

## Files

- `lessons/templates/lessons/lesson_detail.html`: quiz-only markup/styles; inline rules and native modal.
- `static/css/quiz.css`: new scoped mobile/desktop quiz layout, safe-area padding, dynamic viewport height, readable wrapping, feedback and reduced-motion support.
- `static/js/quiz.js`: modal lifecycle, paint-synchronized timer, background pause/resume, close/history cleanup, compact progress/results.
- `lessons/browser_checks.py`: three new quiz browser scenarios and existing quiz assertions updated for Kazakh copy and enabled-choice timing.
- `lessons/test_learning_flow.py`: expected retake label updated to Kazakh.
- `docs/REALTIME_AND_QUIZ_CONTRACTS.md`, `docs/TESTING_AND_QUALITY.md`, and this checkpoint: current behavior/evidence.

## Implemented behavior

Start opens the modal immediately with a loading status; once data arrives, question and choices render in the viewport without scrolling the lesson. Two animation frames precede enabling answers and starting the five-second monotonic deadline. Network waits and brief 180ms feedback do not consume the next question's time. Backgrounding pauses the remaining interval and requires explicit resume. Close restores lesson scroll and start-button focus. Escape closes; browser navigation cleans up and restoration fetches server state.

The compact pinned header shows question count, bounded progress, score, mistakes, countdown, and close. Long choices scroll inside the answer area; exceptionally long questions have their own bounded scroll area. Typical four-choice content fits at tested mobile sizes. Existing fewer-choice vocabulary cases are preserved. Feedback uses selected/green/red states and text; no sounds, confetti, frameworks, or client-side scoring. Completion and three-mistake screens expose retake/restart; previous completion is untouched. Attempt tokens, exact-answer retries, CSRF, idempotency, authoritative scores, and access enforcement remain unchanged.

## Verification

- Django learning/quiz suites: **42 passed**, 7.632s.
- Targeted Chromium suite: **9 passed**, 30.139s. Includes complete pass → next/retake → three mistakes, lost-answer retry, five-second timeout/history restoration, shared-loader recovery, reduced motion, real back navigation, slow start/submit, background/resume and duplicate taps.
- Actual rendered geometry verified at **320×568, 375×667, 390×844, 430×740, 320×480, 1024×768**. Ordinary answers and controls fit; close restores scroll/focus. Separate long-vocabulary case verifies internal scrolling and Escape. External CDNs blocked, so quiz CSS works independently of Bootstrap.
- Screenshots captured in `/tmp/oqyai-quiz-*.png`; mobile short-height, 390px, desktop and long-answer views visually inspected.
- Django system check, JS syntax, and `git diff --check` passed.
- Browser transitions measured approximately **190–198ms** including existing feedback; not a production speed claim. One small local stylesheet added; no additional quiz API round trips.

## Checkpoint history and fixes

Before long runs, checkpoints recorded implemented work and pending tests. Initial viewport checks caught legacy oversized score/timer CSS, which was removed. The old English retake assertion was updated. Scroll checks were adjusted to exclude Selenium's own pre-click scrolling; explicit start-button focus restoration was fixed. All final targeted checks pass.

## Limits / remaining manual checks

Physical iPhone/WKWebView and Android WebView, hardware safe-area insets, OS background suspension, and rotation on real devices remain unverified. Native `dialog`/`showModal` support is required. The five-second rule remains browser-enforced as before; this is not a server timing redesign. Optional streaks were omitted to avoid implying persistent history. Deploy only through the normal reviewed Django/static-file release process; nothing was deployed here.

## November 19 refinement — ready for manual review

This iteration introduced a sky/lavender surface with white question and answer cards, letter badges, three heart-shaped lives, and one numeric countdown. The horizontal bar shows question completion. Correct choices turn green with a checkmark for 500 ms. A wrong choice turns red with a cross while the correct choice turns green for 1,250 ms, including the last mistake. The next countdown begins after the new choices render. Motion-reduction preferences disable transitions while preserving time to read the correction. Result cards hide the timer and offer retry or an authorized next lesson.

The submit response supplies the translation after recording the answer. On replay it supplies the stored choice and outcome. Hearts use the returned mistake count or the terminal reset flag. The final score and answered count survive the reset in the response. The next-lesson link uses the existing access policy. See the [quiz contract](REALTIME_AND_QUIZ_CONTRACTS.md).

**Files edited in this refinement**

- UI: `lessons/templates/lessons/lesson_detail.html`, `static/css/quiz.css`, `static/js/quiz.js`.
- Response fields and next-action availability: `lessons/views.py`.
- Verification: `lessons/browser_checks.py`, `lessons/test_quiz_integrity.py`, `lessons/test_quiz_concurrency.py`, `lessons/test_learning_flow.py`.
- Documentation: this file and `docs/REALTIME_AND_QUIZ_CONTRACTS.md`. The existing testing guide change belongs to the earlier redesign.

**Final verification**

- SQLite quiz integrity and learning suites: **44 passed**.
- Disposable MySQL quiz integrity, learning and real-lock concurrency suites: **50 passed**, including six race tests. These ran against a private Unix socket with networking disabled. The isolated database was removed on exit.
- Chromium quiz scenarios: **8 passed**. Ten correct taps followed immediately by a different tap generated one POST, one point, and no completion. Server tests also submitted ten copies directly. Simultaneous different choices returned the single stored outcome. Retrying a lost wrong-answer response showed the stored correction and spent exactly one heart. The stale-token, third-mistake and retake tests passed.
- Ordinary choices, header and exit fit at **320×480, 320×568, 375×667, 390×844, 430×932, and 1024×768**. Long translations scroll inside the answer area. Reduced-motion styling, background/foreground, timeout, scroll restoration and close were covered.
- Inspected synthetic-data renders for active play, correct and wrong feedback, success and retry. Screenshots are in `/tmp/oqyai-refined-{correct,wrong,pass,fail}.png` and `/tmp/oqyai-quiz-WIDTHxHEIGHT.png`.
- Django system check, JS syntax and diff whitespace passed. Checkpoints were saved before the initial and final runs. The initial MySQL run exposed test data relying on auto-assigned free lesson IDs; the tests now explicitly use those curriculum IDs. Feedback tests poll within the short highlight interval.

Remaining manual check: physical iPhone/WKWebView and Android WebView, especially safe areas and rotation. Local Chromium emulation was used. No database migration, commit, push or deployment was performed.


## November 19 final polish

The lesson start card uses a target, compact time and heart indicators, and a question count from the same vocabulary parser that builds the quiz. The saved result uses its historical denominator even if the lesson changes. Legacy scores with an unknown total show the recorded score alone. The card reserves space for the lesson chat control.

During a question, the header shows the question number as text and the five-second deadline as one 9 px shrinking bar. The bar starts when the choices become usable, freezes on submission, and disappears on the result screen. Reduced motion displays one-second steps. Returning to the tab or reopening the same question uses the original deadline. Tab storage retains the deadline across a reload when available. The existing server submission path records timeouts, mistakes and scores.

Updated files in this pass are the lesson detail template and view, quiz CSS and JavaScript, learning-flow and Chromium tests, this record, and the quiz contract.

**Final verification**

- SQLite learning and quiz integrity suites passed all 44 tests. The same suites plus six concurrency tests passed all 50 tests on disposable MySQL.
- Chromium 157 passed all 11 targeted quiz scenarios. The recorded bar widths decreased to zero, with one timeout POST at five seconds (180 ms test tolerance). Tests also exercised a real tab switch past expiry, reload, reduced motion, frozen feedback, a fresh countdown, rapid taps, lost responses and retakes.
- The start control and ordinary quiz choices fit at 320×480, 320×568, 375×667, 390×844, 430×932 and 1024×768. Screenshots revealed a chat-control overlap on the card. After adding bottom clearance, both CTA edges passed browser hit testing at every size.
- Django system check, JavaScript syntax and diff whitespace checks passed. The four screenshots use disposable test data and are saved as `/tmp/oqyai-polish-{start,active,expiry,retake}.png`.
- Physical iPhone/WKWebView rendering, suspension and safe areas still require device testing. The five-second rule runs in the browser and the server validates and records quiz outcomes.
