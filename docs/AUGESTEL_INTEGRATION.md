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


## Findings from `augestel.com.login.har` (2026-10-14)

The provided capture contains seven requests, all GET requests after a user session was already active. It does **not** contain a login form submission, authentication POST, redirect to an authenticated session, or a response that establishes credentials. Therefore, this HAR is insufficient to implement actual account login.

Observed read-only requests in the capture:

| Method | Path | Status | Response keys observed |
|---|---|---:|---|
| GET | `/Switchfy/test/live-totals` | 200 | `capped`, `senders`, `terminations`, `countries`, `messages`, `ranges`, `countries_total`, `success` |
| GET | `/Switchfy/test/live-history` | 200 | `success`, `records` |
| GET | `/Switchfy/test/termination-meta` | 200 | `success`, `terms` |

The captured requests include a query parameter named `limit` for live-totals/live-history, and `ids` for termination-meta. Values and session headers are intentionally not copied into this document.

Some dashboard requests include a header named `X-CSRF-Token`; this is evidence of a CSRF-related header, not evidence about how the token is obtained, scoped, or refreshed. Do not hardcode its value or reuse it from HAR.

### How to capture the missing login flow

To identify the actual login process, start a **new** DevTools Network recording at the Augestel login page before entering credentials, enable Preserve log, then sign in normally. The capture needs to show the request method/path and response status for the login attempt. Do not send a raw HAR if it contains passwords, session cookies, CSRF values, authorization headers, or tokens; provide a redacted screenshot of the request metadata instead.

Until an approved authentication contract is confirmed, the bot's `auth_method_required` state remains correct and no credentials should be collected by the bot.
