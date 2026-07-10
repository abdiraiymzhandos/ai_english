# Admin access operations

This is a concise operator-facing map of existing access state. It is not a payment ledger or authorization specification. Read [the architecture/access matrix](docs/ARCHITECTURE_AND_CODEBASE.md#access-and-entitlement-matrix) and [security audit](docs/SECURITY_AUDIT.md) before changing access.

## Existing profile state

| State/helper | Current meaning |
| --- | --- |
| `UserProfile.is_paid` / `has_paid_lesson_access()` | Permanent Boolean course access; no start/expiry/source/audit |
| `has_voice_access`, `voice_access_until`, `has_active_voice_access()` | Separate voice entitlement and optional expiry |
| `has_translator_access`, `translator_access_until`, `has_active_translator_access()` | Separate translator entitlement and optional expiry |
| `role` / `is_teacher()` | Student or teacher; currently self-selected at registration |
| `can_use_classroom_teacher_features()` | Teacher role only |
| `can_run_classroom_voice_sessions()` | Teacher role plus active voice access |
| `current_lesson` | Numeric snapshot, not the only progress source |
| `lock_until` / `is_locked()` | Device middleware account lock |
| `UserDevice` | Cookie-derived device rows; not a trustworthy identity control |

Admin actions in `lessons/admin.py` can mark course access, grant/revoke dated voice/translator access, and unlock accounts. They do not create an order, payment, entitlement audit, reviewer record, or reason.

## Safe operational rules

- Identify whether the request concerns course, voice, translator, classroom role, or device lock; these are separate.
- Verify account ownership through an approved process. A matching unverified phone string is insufficient.
- Do not grant course access solely because OCR recognized a receipt; see `SEC-001`.
- Do not use WhatsApp auto-provisioning until critical security tasks are complete.
- Record authorization and reason outside this incomplete admin flow until `DATA-002` adds an audit ledger.
- Never place credentials or private values in screenshots, tickets, commands, or Markdown.
- Check both the page and backing endpoint; UI state alone is not authorization evidence.
- Avoid bulk changes unless explicitly approved, reviewed, and reversible.

## Known failure modes

- Paid course access does not imply voice or translator access.
- Teacher role does not imply live classroom voice access.
- Duplicate/non-canonical phone values can make WhatsApp linking fail or bind incorrectly.
- Device cookie loss can create new rows and eventually lock an account; the lock page currently loses expiry detail after logout (`BUG-003`).
- `current_lesson`, passed `QuizAttempt` rows, and session unlock state can disagree.
- Course copy promises a duration that the Boolean access model cannot enforce.

## Verification after an authorized change

- Confirm the exact profile state and optional expiry.
- Confirm access denial for an adjacent unauthorized state.
- Confirm relevant token/API endpoint, not only template display.
- Confirm no unrelated entitlement changed.
- Record the change and update future entitlement audit data when `DATA-002` exists.
