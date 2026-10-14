# Augestel integration notes

Observed browser request paths from user-provided HAR files:

- Add Number: `POST /Switchfy/client/numbers/request`
- Export: `GET /Switchfy/client/numbers/export`
- Return All: `POST /Switchfy/client/numbers/bulk-return-all`

These are observed website routes, not confirmation of supported public API endpoints. Do not call these browser-only routes with the API key unless the provider's API documentation explicitly lists them.

## Current connection behavior

The bot registers Telegram users and stores a per-user Augestel connection state. The existing Connect Account action records `auth_method_required`; it does not start a browser login and does not establish an API connection.

The user-provided Augestel API documentation states that API requests use Bearer authentication:

```http
Authorization: Bearer YOUR_API_KEY
```

Configuration added to the application:
- `AUGESTEL_API_KEY`: stored as a Pydantic `SecretStr`, read from local environment configuration.
- `AUGESTEL_API_BASE_URL`: defaults to the Base URL documented by the user, `https://augestel.com/api/v1/iprn`.
- `AUGESTEL_INTEGRATION_ENABLED`: remains `false` by default.

The integration client now has a read-only `get_json(path)` foundation that uses the Bearer header, validates HTTPS and the Augestel host, rejects redirects, and avoids printing response bodies or credentials in errors. The documented Base URL is configured, but no live endpoint has been called because resource endpoint paths and schemas have not yet been supplied.

Before implementing feature operations:
1. The API Base URL supplied from the documentation is `https://augestel.com/api/v1/iprn`; copy the endpoint paths and schemas from the official docs.
2. Verify documented request parameters and response schemas with read-only calls first.
3. Keep the API key in local `.env` or a secret manager; never in chat, source code, logs, or the repository.
4. Require explicit confirmation for write actions such as Add Number and Return All.
5. Never blindly retry a timed-out Return All; first determine whether the provider completed it.
6. Do not use browser cookies, CSRF tokens, or challenge payloads for the API client.

Actual Add Number submission, export download, and Return All remain unimplemented and blocked.


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

This capture does not show Add Number, Export, or Return All being triggered. The website form route is not needed when using the documented API-key authentication scheme. Use the API's documented Bearer header rather than scraping website sessions. The exact API Base URL and endpoint contracts still need to be taken from the API documentation; do not guess them. Do not bypass challenge/anti-abuse controls or replay sensitive values from HAR.


## Add Number draft validation (2026-10-14)

The bot now accepts a local draft command:

```text
/addnumber <termination_id> <termination_term_id> <count> <sort_type>
```

The four business fields are based on the observed browser form submission. The command validates identifiers, positive count, and safe sort-type syntax; a conservative local draft ceiling of 1,000 prevents accidental oversized drafts. This ceiling is an application safeguard, not an Augestel limit.

A valid draft is recorded as `draft_prepared_not_sent`. **No network request is sent.** The helper does not accept `_token`, `request_token`, passwords, cookies, or session values. Those fields must never be copied from HAR or supplied by Telegram users. Actual submission remains disabled until provider-approved authentication and endpoint semantics are verified.


## Bearer API client foundation (2026-10-14)

The user-provided Authentication section documents Bearer token authentication: `Authorization: Bearer YOUR_API_KEY`. The application configuration and a read-only JSON GET helper have been added, but the API key itself must only be stored in the user's local `.env` or deployment secret store.

The documented Base URL is now configured as `https://augestel.com/api/v1/iprn`. Before enabling integration, verify the specific resource endpoint paths and request/response schemas. Do not use `/Switchfy/client/numbers/request`, `/Switchfy/client/numbers/export`, or `/Switchfy/client/numbers/bulk-return-all` in the API client merely because they were seen in browser HAR files.

Example local configuration (do not commit `.env`):

```dotenv
AUGESTEL_API_BASE_URL=https://augestel.com/api/v1/iprn
AUGESTEL_API_KEY=put_regenerated_key_here_locally
AUGESTEL_INTEGRATION_ENABLED=false
```

The API Base URL is taken directly from the documentation supplied by the user. When a documented read-only endpoint is confirmed, it can be called via `AugestelClient.get_json()`. Add Number, export download, and Return All remain guarded placeholders until their API endpoints, payloads, scopes, and response formats are verified.

**Key rotation:** the earlier screenshot showed an API key visibly. Treat that key as exposed and regenerate it in the Augestel dashboard before using any key locally.
