# ADMIN_ACCESS_OPERATIONS.md

Use this with `PROJECT_CONTEXT.md`, `FEATURES_MAP.md`, and `KNOWN_RISKS.md`.

## Access Model At A Glance

| Field / Mechanism | Purpose | Notes |
| --- | --- | --- |
| `UserProfile.is_paid` | Paid lesson access | Does not automatically grant voice or translator access |
| `UserProfile.has_paid_lesson_access()` | Paid lesson access check | Preferred runtime check where paid lesson gating is needed |
| `UserProfile.has_voice_access` | Voice lesson access | Checked with `voice_access_until` |
| `UserProfile.voice_access_until` | Voice expiry | `has_active_voice_access()` is the real check |
| `UserProfile.has_translator_access` | Translator assistant access | Separate from paid/voice |
| `UserProfile.translator_access_until` | Translator expiry | `has_active_translator_access()` is the real check |
| `UserProfile.current_lesson` | Progress snapshot | Not the only source of truth; `QuizAttempt` also matters |
| `UserProfile.lock_until` | Account/device lock | Enforced by middleware |
| `UserProfile.role` | Teacher/student distinction | Current local WIP; verify commit state before treating as stable baseline |
| `UserProfile.can_use_classroom_teacher_features()` | Teacher classroom pages | Preferred runtime check for dashboard/group management |
| `UserProfile.can_run_classroom_voice_sessions()` | Teacher classroom live session access | Teacher role + active voice access |
| `UserDevice` rows | Device count enforcement | More than 3 devices locks the account |

## Where Access Behavior Is Controlled
- `lessons/models.py`
  - `UserProfile` helpers define paid lesson access, active voice/translator access, lock state, and classroom teacher/session access.
- `lessons/views.py`
  - Lesson gating, voice token gating, translator token gating, profile behavior.
- `lessons/templates/lessons/profile.html`
  - User-facing mirror of current access state and upgrade CTAs. Useful when UI looks wrong but backend flags are correct.
- `lessons/middleware.py`
  - Device lock and forced logout path.
- `lessons/admin.py`
  - Manual access/provisioning actions.
- `lessons/management/commands/grant_voice_access.py`
- `lessons/management/commands/revoke_voice_access.py`

## Admin Actions Present In Code
- `unlock_accounts`
  - Clears `lock_until` and deletes device rows through `profile.unlock()`.
- `mark_as_paid`
  - Sets `is_paid=True`.
- `grant_voice_access_30_days`
- `grant_voice_access_90_days`
- `revoke_voice_access`
- `grant_translator_access_30_days`
- `grant_translator_access_90_days`
- `revoke_translator_access`

## Important Operational Reality
- Paid access, voice access, and translator access are separate.
- A user can be paid but still lack voice or translator access.
- Voice access has both a boolean and an expiry date.
- Translator access has both a boolean and an expiry date.
- Lesson unlock progression is not admin-driven in normal flow; it comes from `QuizAttempt` plus session state.
- Current local classroom WIP ties teacher classroom pages to `can_use_classroom_teacher_features()` and live classroom sessions to `can_run_classroom_voice_sessions()`.
- New WhatsApp sales automation only grants the existing paid-course flag:
  - high-confidence receipt validation sets `UserProfile.is_paid=True`
  - it does not automatically grant voice or translator access

## How Lesson Access / Unlock Provisioning Appears To Work
- Free lessons are always available for `{1,2,3,251,252,253}`.
- Unpaid users are gated off premium lesson ranges.
- `QuizAttempt` is the main record of passed lessons.
- `request.session['passed_lessons']` also affects visible unlock state.
- `current_lesson` is updated after quiz progression, but it is not the only thing the app checks.

## Common Failure Modes
- User is marked paid, but voice lesson still fails because `has_voice_access` is false or expired.
- User is marked paid, but translator assistant still fails because translator access is separate.
- Access looks correct in UI, but token endpoint rejects the user.
- Device lock logs the user out and gets mistaken for a permission bug.
- `UserProfile` is missing expected values because middleware created it lazily.
- Current local teacher/classroom access behaves differently from stable baseline; verify commit state.

## Safe Operational Guidance
- Inspect the actual `UserProfile` row before changing code.
- Identify which feature is failing: paid lessons, voice, translator, account lock, or classroom.
- Start with the relevant `UserProfile` helper before editing views or templates.
- Change the smallest access mechanism needed.
- Do not implicitly couple unrelated flags unless that is an explicit product decision.
- Verify both the user-facing page and the backing API/token endpoint.

## Where To Inspect First For Access Issues
- `lessons/models.py`
- `lessons/views.py`
- `lessons/admin.py`
- `lessons/middleware.py`
- relevant template showing the feature CTA

## Questions To Answer Before Changing Access Logic
- Is the failure about paid lesson access, voice access, translator access, device lock, or classroom WIP?
- Should the fix change stable baseline behavior or only local WIP behavior?
- Is the UI wrong, the backend wrong, or both?
- Which user states must continue to work: guest, unpaid, paid, expired-access, teacher?
- Should the change affect provisioning rules, runtime checks, or just display logic?
- Is there an operational/admin-only fix that is safer than changing code?
