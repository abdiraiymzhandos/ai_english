# WhatsApp agent setup — sanitized and deprecated

This document previously contained live-looking operational credentials/identifiers and time-sensitive external state. Treat any exposed credential as compromised and rotate it under `SEC-005`. Never restore secret or private values to Markdown.

## Current configuration names

The code reads environment variables for:

- WhatsApp access token, phone-number ID, business-account ID, webhook verify token, and Graph API version;
- Telegram bot token/chat ID;
- OpenAI API key;
- application base URL;
- course price and payment-recipient fields.

Values belong in a protected deployment secret store, not Git, documentation, shell history, or command output. A future sanitized `.env.example` should contain names/placeholders only (`DEVOPS-002`).

## Security status

Do **not** enable automatic receipt provisioning as a trusted production flow:

- webhook POST signatures are not validated (`SEC-002`);
- OCR-only receipts can be forged/replayed (`SEC-001`);
- sandbox recipient mutation can send replies to a different number (`SEC-003`);
- initial passwords can be messaged and persisted in plaintext (`SEC-004`);
- raw payloads/receipts/messages have no complete retention policy (`SEC-012`).

## Safe verification boundary

Automated tests must mock Meta/OpenAI/Telegram and use fake values. A live webhook/send/phone-registration test changes external state and requires explicit authorization, a controlled non-production account/recipient, redacted logs, and a rollback/cleanup plan.

The current phone-registration command accepts a sensitive PIN through a CLI argument and prints its payload. Do not run it until `SEC-004` removes secret output and an operator-approved input method exists.

Architecture: [docs/AI_INTEGRATIONS.md](docs/AI_INTEGRATIONS.md). Security: [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md). Deployment: [docs/ENVIRONMENT_AND_OPERATIONS.md](docs/ENVIRONMENT_AND_OPERATIONS.md).
