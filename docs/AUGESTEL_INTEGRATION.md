# Augestel integration notes

Observed browser request paths from user-provided HAR files:

- Add Number: `POST /Switchfy/client/numbers/request`
- Export: `GET /Switchfy/client/numbers/export`
- Return All: `POST /Switchfy/client/numbers/bulk-return-all`

These are observed website routes, not confirmation of a supported public API.

## Current connection behavior

The bot registers Telegram users and stores a per-user Augestel connection state. Clicking Connect Account records `auth_method_required`. This is **not** a successful login and does not create a live Augestel session.

Before implementing actual login:
1. Confirm Augestel permits the integration and identify an approved authentication method.
2. Confirm the supported account-scoped auth method and account isolation strategy.
3. Identify how CSRF/request tokens are obtained, scoped, and refreshed without logging or hardcoding them.
4. Verify request payloads and response schemas using non-destructive operations first.
5. Do not ask users to send their passwords, cookies, or browser tokens via Telegram.
6. Require explicit confirmation for Add Number and Return All.
7. Never blindly retry a timed-out Return All; determine whether the prior operation completed.
8. Never commit HAR files, cookies, bearer tokens, passwords, or export data.

The adapter intentionally raises an error rather than sending guessed requests until the above are confirmed.
