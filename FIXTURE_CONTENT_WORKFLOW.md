# FIXTURE_CONTENT_WORKFLOW.md

Use this with `PROJECT_CONTEXT.md`, `FILE_MAP.md`, and `KNOWN_RISKS.md`.

## Relevant Files

| File | What It Appears To Contain | Notes |
| --- | --- | --- |
| `lessons/fixtures/lessons.json` | Core lesson content | Main repo-controlled course content snapshot |
| `lessons/fixtures/quiz_questions.json` | Quiz question rows | Derived from vocabulary structure; not ideal as first-edit target |
| `lessons/fixtures/explanations.json` | Explanation rows with `text` and `audio_url` | Can drift after lesson edits or AI regeneration |
| `lessons/fixtures/quiz_attempts.json` | Runtime progress snapshot | Usually not source content |
| `lessons/fixtures/user_profiles.json` | Runtime/access snapshot | Operational data, not lesson content |
| `lessons/fixtures/user_devices.json` | Runtime device snapshot | Operational data |
| `lessons/fixtures/leads.json` | Lead capture data | Operational/marketing data |
| `analyze_lessons.py` | Legacy/local analysis script | Verify relevance before using |

## Data Shape Notes
- `Lesson` content is structured as:
  - `title`
  - `content`
  - `vocabulary`
  - `grammar`
  - `dialogue`
- `QuizQuestion` rows point to `Lesson`.
- `Explanation` rows are unique per `(lesson, section)`.
- `QuizAttempt.user_id` is a string, not a foreign key.
- Current local snapshot counts observed in repo:
  - `lessons.json`: `300` lessons
  - `quiz_questions.json`: `1042` rows
  - `explanations.json`: `227` rows
  - `user_profiles.json`: `49` rows

## Confirmed Quirks
- Fixture files are polluted at the top by settings import output.
- Confirmed example:
  - first line of `lessons/fixtures/lessons.json` is `✅ OpenAI API кілті сәтті жүктелді!`
- This means current fixture dumps are not clean JSON from byte 0.
- Root cause is likely the `print(...)` inside `english_course/settings.py`.

## How Content And Quiz Generation Interact
- `lessons/views.py::generate_quiz_questions()`
  - Deletes existing `QuizQuestion` rows for a lesson.
  - Rebuilds them from `Lesson.vocabulary`.
- Parsing assumption
  - Vocabulary lines are split using the delimiter `" – "`.
- `lessons/views.py::start_quiz()`
  - Calls `generate_quiz_questions()` during request handling.
- Implication
  - Content formatting changes can immediately affect runtime quiz generation.

## How Explanations Interact With Content
- `lessons/views.py::explain_section()`
  - Generates explanation text with OpenAI.
  - Synthesizes audio via `english_course/utils/realtime_tts.py`.
  - Stores/updates `Explanation`.
- Implication
  - If a lesson changes, existing `Explanation` content and `audio_url` may become stale.

## Scripts / Utilities That Touch Content
- `analyze_lessons.py`
  - Not standard Django content workflow.
  - Uses hard-coded Postgres credentials and `psycopg2`.
  - Verify relevance before relying on it.
- Django admin for `Lesson`
  - Exists via `lessons/admin.py`.
- Fixture dumps
  - Currently unsafe/noisy until settings import print is handled or filtered.

## Safe Workflow For Editing Content
1. Decide the source of truth for this task.
   - Repo fixture change.
   - Admin/DB content change.
   - One-off runtime regeneration.
2. If changing lesson content in repo, start with `lessons/fixtures/lessons.json`.
3. Preserve lesson IDs unless the task explicitly requires a migration of references.
4. Validate vocabulary formatting, especially the `" – "` delimiter.
5. Treat `quiz_questions.json` as derived data unless you intentionally want to freeze generated output.
6. Treat `explanations.json` as generated/stale-prone content unless you intentionally want to update stored explanation output.
7. If you need fresh dumps, fix or filter the settings print side effect first.

## Common Mistakes To Avoid
- Hand-editing `quiz_questions.json` without matching `Lesson.vocabulary`.
- Editing lesson text and forgetting explanation drift.
- Assuming current fixture files are clean JSON.
- Changing lesson IDs casually.
- Treating runtime/operational fixture snapshots as stable authored content.
- Using `analyze_lessons.py` as if it were part of the normal app workflow.

## Verify Data Integrity After Edits
- Confirm affected fixture is valid JSON.
- Confirm the first line is not polluted when producing new dumps.
- Confirm lesson IDs and `model` labels are unchanged unless intentionally migrated.
- Confirm representative vocabulary lines still parse into quiz questions.
- Confirm a representative lesson quiz still starts successfully.
- Confirm explanation records for changed lessons are refreshed or consciously left stale.
