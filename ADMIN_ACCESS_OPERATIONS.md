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

Admin actions in `lessons/admin.py` can mark course access, grant/revoke dated voice/translator access, and unlock accounts. The verified course payment action records the first unpaid-to-paid transition and its reviewer. Ordinary access edits are separate. See the [sales and analytics guide](docs/SALES_ANALYTICS.md).

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
- Independent browser or WebView cookie stores, private browsing and cleared cookies can produce separate identities on the same phone.
- `current_lesson`, passed `QuizAttempt` rows, and session unlock state can disagree.
- Course copy promises a duration that the Boolean access model cannot enforce.

## Verification after an authorized change

- Confirm the exact profile state and optional expiry.
- Confirm access denial for an adjacent unauthorized state.
- Confirm relevant token/API endpoint, not only template display.
- Confirm no unrelated entitlement changed.
- Record the change and update future entitlement audit data when `DATA-002` exists.

## Device lock rollout and recovery

Previously the fourth identity was inserted before checking the three-device limit. The five-day deadline eventually became inactive while all four device rows survived. A later request counted those stale rows and started another five days.

The default `MAX_ACCOUNT_DEVICES=2` admits the first two browser/app cookie identities. A new identity at capacity starts a single five-day UTC deadline. Its device row is never inserted. Known identities on unlocked legacy accounts continue working even if their existing count exceeds the new limit. Active locks apply across all learner sessions. Retry attempts preserve the original deadline. At or after expiry the next relevant request clears the deadline and registry together. An authenticated request may then register its current identity in that same transaction. The read-only preflight and manual cleanup require no scheduled job.

Changes to an account's registry serialize on its profile row in MySQL. File-backed SQLite reserves a writer before modifying the registry. Ordinary requests for an admitted identity read its membership and profile together. Login and registration forms can initialize an HttpOnly, SameSite=Lax cookie without adding a row. Successful authentication checks admission before returning the login redirect. Simultaneous requests with the same authenticated session and no cookie derive the same opaque identity. HTTPS uses a Secure cookie. Active staff and superusers are exempt so operators retain admin access. A teacher role alone grants no exemption.

A cookie identifies a browser store. Chrome and Safari, different app installs, and private profiles can count separately. Two independent requests with neither a common cookie nor a common session have no shared browser identity. Clearing a registry does not revoke Django sessions globally. The blocked session is logged out. Other learner sessions are checked again on their next protected request, and can register afresh after recovery. Previously authorized requests already in flight may complete.

**Owner unlock.** Open **Admin → User profiles → the learner**. Check identity, device count and lock status. Select **Құлыпты ашу және құрылғыларды тазалау**. This CSRF-protected POST clears only that profile's lock and device rows, reports the number removed and creates a Django Admin history entry. Repeating it reports zero unless the learner has since re-enrolled. Both individual and bulk unlock require an active superuser with admin access. The deadline is read-only in the regular profile form. The **Құрылғы саны → Шектен көп** list filter identifies profiles above the configured cap for owner review.

**Learner screen.** After logout the anonymous Django session holds a reference to the exact lock. The page checks the current stored deadline, ignores URL-supplied identity, and sends a private, no-store response. The server renders the unlock date in Asia/Almaty and the remaining time. JavaScript advances the countdown using monotonic elapsed time, then rechecks the server at expiry, on return from the background and on browser-history restoration. Missing context shows a neutral login/help page. Support uses the existing official WhatsApp contact. Neither the page nor its URL contains a learner's phone or username.

### Production preflight and activation

The owner's earlier production snapshot found 14 accounts above three registrations, all with expired locks, and zero active locks. It did not count accounts with exactly three. Obtain fresh aggregate counts on PythonAnywhere before changing the policy. Run this read-only check from the existing checkout before pulling the patch.

```bash
cd /home/abdiraiymzhandos/ai_english
venv/bin/python manage.py shell -c 'from django.db import connection; from django.db.models import Count; from django.utils import timezone; from lessons.models import UserDevice,UserProfile; assert connection.vendor=="mysql"; n=timezone.now(); sizes=UserDevice.objects.values("user_id").annotate(n=Count("pk")); expired=UserProfile.objects.filter(lock_until__lte=n); print("over_two",sizes.filter(n__gt=2).count(),"over_three",sizes.filter(n__gt=3).count(),"expired",expired.count(),"devices_on_expired",UserDevice.objects.filter(user__profile__lock_until__lte=n).count(),"active",UserProfile.objects.filter(lock_until__gt=n).count())'
```

**Publication after owner review.** Run these commands on local main.

```bash
cd ~/english_platform/english_course
git status --short --branch
git diff
git add -- ADMIN_ACCESS_OPERATIONS.md docs/BACKLOG.md english_course/settings.py \
  lessons/{admin,browser_checks,middleware,models,test_device_access,views}.py \
  lessons/services/device_access.py lessons/management/commands/reconcile_device_locks.py \
  lessons/templates/admin/lessons/userprofile/change_form.html lessons/templates/lessons/account_locked.html \
  static/css/account-locked.css static/js/account-locked.js
git diff --cached
git diff --cached --check
git commit -m "fix: expire device locks atomically and add superuser recovery"
git push origin main
```

1. Start with `MAX_ACCOUNT_DEVICES=3` in the existing production web environment or its loaded .env. An exported process setting takes precedence over .env. Keep the current restricted backup available if device registrations must be recovered later.
2. Pull the reviewed change and prepare the web app in the PythonAnywhere Bash console.

   ```bash
   cd /home/abdiraiymzhandos/ai_english
   git status --short --branch
   git pull --ff-only origin main
   venv/bin/python manage.py check
   venv/bin/python manage.py makemigrations --check --dry-run
   venv/bin/python manage.py migrate --plan
   venv/bin/python manage.py collectstatic --noinput
   venv/bin/python manage.py reconcile_device_locks --dry-run
   ```

   Check that the plan is empty and the preview says `limit=3`. No dependency installation or database migration is required for this release. Select **Web → Reload**. The Always-on Task handles notifications and analytics and does not participate in this policy.
3. Review the preview. **Only after explicit owner approval**, reconcile the currently expired locks. Each candidate's deadline is rechecked under lock, so a simultaneous login, manual unlock or new active lock is respected.

   ```bash
   venv/bin/python manage.py reconcile_device_locks --apply
   venv/bin/python manage.py reconcile_device_locks --dry-run
   ```

   The apply output reports actual profiles cleared and rows removed. Counts can differ from preflight as learners return. Previously unlocked over-limit profiles and currently active locks remain intact. A second apply ordinarily removes zero.
4. Preview the intended threshold with `MAX_ACCOUNT_DEVICES=2 venv/bin/python manage.py reconcile_device_locks`. Set `MAX_ACCOUNT_DEVICES=2` in the active production configuration, select **Web → Reload**, and confirm `venv/bin/python manage.py reconcile_device_locks` reports the intended cap. Review any grandfathered accounts with the admin over-limit filter. Coordinate an individual reset with the owner and learner when appropriate. No blanket registry reset is necessary.
5. Use a controlled learner in separate browser profiles to verify two admissions, one lock on the third attempt, a stable local unlock time on retry, and the admin button and history entry. Check normal login and a protected lesson after the targeted unlock. Verify the support destination and return-to-login control in the deployed WebViews.

**Rollback.** Set `MAX_ACCOUNT_DEVICES=3` and select **Web → Reload** to restore the previous allowance while retaining safe expiry. This does not shorten existing locks. The owner may unlock an affected account individually. If a code rollback is essential, revert the reviewed release commit on local main with `git revert <release-commit>`, push it, pull with `git pull --ff-only origin main` on PythonAnywhere, collect static files and reload the web app. Reverting code to the old middleware reintroduces the stale-row bug. A Git rollback cannot recreate device rows already cleared.
