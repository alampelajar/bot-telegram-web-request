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


## Findings from `augestel.com.login(1).har` (2026-10-14)

The second capture contains 10 requests, but it still does **not** include a login form submission or an authentication response:

- Three static JSON/media resources were fetched.
- The dashboard made read-only GET requests to live totals, live history, termination metadata, and latest notifications, each returning HTTP 200.
- Two POST requests were sent to challenge-related paths, `/cap/start` and `/cap/puzzle`. These appear to be part of a challenge flow, not a login form submission. Their tokens, image/challenge payloads, and proof values are deliberately omitted from this documentation.

There is no captured request that conclusively establishes how a username/password login is submitted or how an authenticated session is created. Do not implement or attempt to bypass the challenge flow based on this HAR. Use an Augestel-supported authentication mechanism or obtain guidance from the provider. If further capture is needed, capture from a fresh unauthenticated login page and share only a redacted screenshot of request metadata—not a raw HAR containing challenge tokens or session data.


## Findings from `augestel.com.login(2).har` (2026-10-14)

The latest capture contains 56 requests and **does** include the normal login form submission:

| Step | Method | Path | Status | Observation |
|---|---|---|---:|---|
| Login submission | POST | `/Switchfy/login` | 302 | Form body contains fields named `_token`, `email`, and `password`; field values are intentionally omitted. Redirects to `/Switchfy`. |
| Landing redirect | GET | `/Switchfy` | 302 | Redirects to `/Switchfy/test/live-sms`. |
| Live SMS page | GET | `/Switchfy/test/live-sms` | 200 | Page content loads successfully. |
| Live totals | GET | `/Switchfy/test/live-totals` | 200 | JSON response loaded. |
| Live history | GET | `/Switchfy/test/live-history` | 200 | JSON response loaded. |
| Termination metadata | GET | `/Switchfy/test/termination-meta` | 200 | JSON response loaded. |
| Live SMS stream | GET | `/live-sms` | 101 | WebSocket upgrade succeeded. |

The redirects and subsequent successful page/API loads are consistent with a successful interactive login. However, the HAR does not include `Cookie` or `Set-Cookie` headers, so it does not establish how session cookies are issued or persisted; this may reflect how the capture was exported. Some read-only API requests include an `X-CSRF-Token` header, but its source, lifetime, and scope remain unverified.

**Security note:** this HAR includes the login request body with an email/password form. Do not commit or forward the raw HAR, and never copy its credential, CSRF, or session values into source code, bot messages, logs, or documentation. If the HAR was shared or stored somewhere not trusted, change the account password and revoke active sessions where Augestel provides that option.

This capture does not show Add Number, Export, or Return All being triggered. The login path is now observed, but it is still a website form route—not confirmation of a supported public API or permission to automate password-based login. Before implementing authentication, confirm Augestel's approved integration method and session-handling rules. Do not bypass challenge/anti-abuse controls or replay sensitive values from HAR.
