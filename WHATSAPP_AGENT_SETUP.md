# WHATSAPP_AGENT_SETUP.md

This repo was reviewed against these root docs before implementation:
- `PROJECT_CONTEXT.md`
- `FILE_MAP.md`
- `FEATURES_MAP.md`
- `KNOWN_RISKS.md`
- `TASK_PLAYBOOK.md`
- `ENVIRONMENT_DEPLOYMENT.md`
- `ADMIN_ACCESS_OPERATIONS.md`
- `CLASSROOM_ARCHITECTURE.md`
- `FIXTURE_CONTENT_WORKFLOW.md`
- `CLASSROOM_MVP_NOTES.md`
- `VOICE_LESSON_README.md`

## What Was Added
- New isolated Django app: `whatsapp_agent`
- Meta webhook endpoint: `GET/POST /api/whatsapp/webhook/`
- Models for WhatsApp leads, messages, events, and receipts
- Telegram admin alerts with deduplication
- OpenAI-driven WhatsApp sales replies for inbound text messages
- WhatsApp outbound text + template sending via Cloud API
- Receipt download + OCR/PDF parsing + conservative confidence scoring
- Automatic paid-course provisioning through the existing `lessons.UserProfile.is_paid` path
- Management commands:
  - `python3 manage.py whatsapp_test_send --to <phone> --text "<msg>"`
  - `python3 manage.py whatsapp_test_send --to <meta-test-input> --template hello_world`
  - `python3 manage.py whatsapp_debug_lead --phone <phone>`
  - `python3 manage.py whatsapp_process_receipt --lead <id>`
  - `python3 manage.py whatsapp_register_phone --pin <6-digit-pin>`

## Existing Access Logic Reused
- Existing OpenAI key/config: `settings.OPENAI_API_KEY`
- Existing auth model: Django `auth.User`
- Existing profile/access model: `lessons.UserProfile`
- Existing paid-course entitlement path: `UserProfile.is_paid` / `has_paid_lesson_access()`

No new OpenAI API-key path was introduced.

## Required Env Vars
Set these in the deployed environment:

```bash
OPENAI_API_KEY=...
SECRET_KEY=...

WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=1086276117905375
WHATSAPP_WABA_ID=1542143414584433
WHATSAPP_WEBHOOK_VERIFY_TOKEN=oqyai_whatsapp_verify_2026

TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=8409596705

APP_BASE_URL=https://www.oqyai.kz
KASPI_RECEIVER_PHONE=+77472445338
KASPI_RECEIVER_NAME=Әбдірайым Жақсылық Байсафарұлы
COURSE_PRICE_KZT=25000
```

Optional:

```bash
WHATSAPP_GRAPH_API_VERSION=v23.0
WHATSAPP_AGENT_OPENAI_MODEL=gpt-5
DEBUG=0
USE_MYSQL=1
MYSQL_DATABASE=...
MYSQL_USER=...
MYSQL_PASSWORD=...
MYSQL_HOST=...
MYSQL_PORT=3306
```

Project config note:
- database selection is now env-driven in `english_course/settings.py`
- local development can leave `USE_MYSQL` unset or set `USE_MYSQL=0` to keep SQLite
- PythonAnywhere production should set `USE_MYSQL=1` plus the `MYSQL_*` env vars
- manual comment/uncomment of database blocks in `settings.py` is no longer needed

## Meta Webhook Config
- Callback URL: `https://www.oqyai.kz/api/whatsapp/webhook/`
- Verify token: `oqyai_whatsapp_verify_2026`
- App name: `OqyAI Sales Agent`
- App ID: `856637317456096`
- Phone Number ID: `1086276117905375`
- WABA ID: `1542143414584433`

## Meta Test Recipient Gotcha
- Meta API Setup test sends can require the exact test-recipient `input` value shown in Meta, not the resolved `wa_id`.
- Current known working example:
  - Meta test recipient input: `787781029394`
  - Meta-resolved actual `wa_id`: `77781029394`
  - Working template send: `python3 manage.py whatsapp_test_send --to 787781029394 --template hello_world`
- Important:
  - do not replace the Meta test-recipient input with the shorter `wa_id` when running the template smoke test
  - the app preserves the exact Meta test-recipient input for template test sends
  - inbound webhook replies are different: they should answer the active chat using the inbound `wa_id` / lead phone (`77781029394` or normalized `+77781029394` in the DB), not the raw Meta API Setup input
- This is separate from the business production number `+77471095715`, which may still require Meta review/registration before real outbound production sending works

## Inbound Reply Flow
- Manual template smoke test:
  - use the raw Meta API Setup recipient input exactly as shown in Meta
  - current working example: `python3 manage.py whatsapp_test_send --to 787781029394 --template hello_world`
- Real webhook conversation reply:
  - Meta sends an inbound message webhook with the actual sender `wa_id`
  - the app stores/updates `WhatsAppLead` and `WhatsAppMessage`
  - the app calls OpenAI using the existing project `OPENAI_API_KEY`
  - the app sends a normal WhatsApp text reply back to the inbound `wa_id` inside the 24-hour customer service window
  - the app records outbound success or failure in `WhatsAppMessage` and `WhatsAppAgentEvent`
- Main behavior is now OpenAI-first for normal inbound text messages.
- The short hardcoded reply is only a fallback if OpenAI fails.

## Production Number Registration
- Current state:
  - the production number `+77471095715` can be added and phone-ownership verified in Meta UI
  - that does not mean it is registered for Cloud API sending yet
  - if Meta still shows the number as `not registered`, you still need the Graph API registration call
- Registration endpoint:
  - `POST https://graph.facebook.com/v23.0/{WHATSAPP_PHONE_NUMBER_ID}/register`
- Request body:
  - `{"messaging_product":"whatsapp","pin":"<6-digit-pin>"}`
- PIN rule:
  - for first registration, use the 6-digit PIN you want Meta to store as the number’s two-step verification PIN
  - if the number already has two-step verification enabled, use that existing 6-digit PIN

Recommended command from this repo:

```bash
python3 manage.py whatsapp_register_phone --pin 123456
```

The command reads:
- `WHATSAPP_ACCESS_TOKEN` from settings/env
- `WHATSAPP_PHONE_NUMBER_ID` from settings/env
- `WHATSAPP_GRAPH_API_VERSION` from settings/env if set, otherwise `v23.0`

It prints:
- the exact URL called
- the HTTP status code
- the full Meta response body

Equivalent curl flow using env vars only:

```bash
curl -sS -X POST "https://graph.facebook.com/v23.0/${WHATSAPP_PHONE_NUMBER_ID}/register" \
  -H "Authorization: Bearer ${WHATSAPP_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"messaging_product":"whatsapp","pin":"123456"}'
```

Expected next step:
- after a successful response, refresh the Meta UI and the production number should move out of `not registered`
- once that is done, outbound sends can use the production phone number ID already configured in env

## Receipt Automation Behavior
- Image receipts: OCR via local Tesseract (`rus+kaz+eng`)
- PDF receipts: text extraction via `pypdf`
- Validation checks:
  - amount `25000`
  - receiver phone `+77472445338`
  - receiver name approximate match to `Әбдірайым Жақсылық Байсафарұлы`
  - timestamp if available
- High confidence:
  - existing account found by `UserProfile.phone` -> set `is_paid=True`
  - no account found -> create `auth.User` + `UserProfile`, set `is_paid=True`
- Low confidence or parser failure:
  - send Telegram alert
  - do not silently grant access

## How To Test
1. Apply migrations:
   `python3 manage.py migrate`
2. In Meta developer console, point the webhook to:
   `https://www.oqyai.kz/api/whatsapp/webhook/`
3. Run the outbound template smoke test with the exact Meta API Setup test-recipient input:
   `python3 manage.py whatsapp_test_send --to 787781029394 --template hello_world`
4. Expected result for the template smoke test:
   - Meta accepts the request
   - the payload `to` value stays `787781029394`
   - Meta may report the actual `wa_id` separately as `77781029394`
5. Use the current WhatsApp test number:
   `+15556330160`
6. Send an inbound text such as:
   `Қалай сатып аламын?`
7. Verify:
   - `WhatsAppLead` and `WhatsAppMessage` rows are created
   - OpenAI generates the normal reply for text messages
   - payment-intent alert reaches Telegram when applicable
   - reply is sent back through WhatsApp to the inbound `wa_id`
   - outbound success/failure is logged in `WhatsAppAgentEvent`
8. Send a receipt image or PDF.
9. Verify:
   - `WhatsAppReceipt` is stored
   - confidence is computed
   - either paid access is granted or Telegram escalation is sent

Useful local commands:

```bash
python3 manage.py test whatsapp_agent
python3 manage.py check
python3 manage.py whatsapp_test_send --to 787781029394 --template hello_world
python3 manage.py whatsapp_debug_lead --phone 77781029394
python3 manage.py whatsapp_register_phone --pin 123456
```

## Temporary vs Permanent Token
- The code reads `WHATSAPP_ACCESS_TOKEN` from env only.
- When moving from a temporary token to a permanent token:
  1. Update the env var
  2. Restart the Django process
  3. Re-test outbound send with `whatsapp_test_send`

No code changes are required for token rotation.

## Production Registration Note
- The business production number `+77471095715` is currently in the exact state where it can be added/verified in Meta UI but still remain unregistered for Cloud API until `/register` is called.
- The integration is built so the current Meta test-recipient setup can work immediately even when the production number is still separate and not fully registered.
- Once the production number is registered in Cloud API, only env/config changes should be needed.

## Current Scope Note
- Existing website templates still contain older hard-coded WhatsApp CTA links.
- Those public CTA links were not changed in this task because the new production Cloud API number is not fully registered yet.
- The new agent is ready behind the webhook/API integration and can be switched into the public flows later without architectural changes.
- Keep the distinction clear:
  - Meta template testing currently works through the test setup input `787781029394`
  - real inbound-reply traffic should answer the active sender `wa_id` such as `77781029394`
  - the separate OqyAI production number is still `+77471095715` and may still need Meta review/registration work before broader rollout
