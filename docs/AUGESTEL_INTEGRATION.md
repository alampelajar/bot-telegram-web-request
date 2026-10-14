# Augestel integration notes

Observed browser request paths from user-provided HAR files:

- Add Number: `POST /Switchfy/client/numbers/request`
- Export: `GET /Switchfy/client/numbers/export`
- Return All: `POST /Switchfy/client/numbers/bulk-return-all`

These are observed website routes, not confirmation of supported public API endpoints. Do not call these browser-only routes with the API key unless the provider's API documentation explicitly lists them.

## Current connection behavior

The bot stores one Augestel API-key connection per Telegram user. The user starts `/connect` in a private bot chat and submits their API key after a warning. The bot validates the key against read-only `GET /numbers`, attempts to delete the source message, and stores only Fernet ciphertext linked to that Telegram user. The API key is never echoed or written to operation history. Message deletion is best-effort and is not guaranteed.

The user-provided Augestel API documentation states that API requests use Bearer authentication:

```http
Authorization: Bearer YOUR_API_KEY
```

Configuration added to the application:
- `AUGESTEL_API_BASE_URL`: defaults to `https://augestel.com/api/v1/iprn`.
- `API_KEY_ENCRYPTION_KEY`: Fernet master key stored in the operator's environment, not in the database or chat.
- `AUGESTEL_INTEGRATION_ENABLED`: remains `false` by default and must be enabled by the operator to allow the API connection flow.
- Each user's Augestel API key is stored in `website_accounts.api_key_encrypted` as ciphertext. No process-wide API key is used.

The integration client now has a read-only `get_json(path)` foundation that uses the Bearer header, validates HTTPS and the Augestel host, rejects redirects, and avoids printing response bodies or credentials in errors. The Base URL and the documented My Numbers endpoint are configured; the endpoint is exercised using mocked tests, not a live call from this development process.

Before implementing remaining feature operations:
1. The API Base URL supplied from the documentation is `https://augestel.com/api/v1/iprn`; continue using endpoint paths and schemas from the official docs.
2. Verify documented request parameters and response schemas with read-only calls first.
3. Users submit API keys only in a private bot chat as part of the explicit `/connect` flow. Never post keys in groups, screenshots, source code, logs, this chat, or the repository. The bot attempts to delete the submitted message but cannot guarantee deletion. The encryption master key belongs in the operator's secret manager or local `.env`, not in the database.
4. Require explicit confirmation for write actions such as Add Number and Return All.
5. Never blindly retry a timed-out Return All; first determine whether the provider completed it.
6. Do not use browser cookies, CSRF tokens, or challenge payloads for the API client.

Add Number and Return All now have guarded custom adapters targeting the website routes observed in HAR. They remain disabled by default because those routes are not in the published API v1 docs, and their acceptance of Bearer API keys has not been verified. Export download remains blocked pending its response contract. The read-only My Numbers endpoint is implemented as described below.


## Findings from `augestel.com.login.har` (2026-10-14)

The provided capture contains seven requests, all GET requests after a user session was already active. It does **not** contain a login form submission, authentication POST, redirect to an authenticated session, or a response that establishes credentials. Therefore, this HAR is insufficient to implement actual account login.

Observed read-only requests in the capture:

| Method | Path | Status | Response keys observed |
|---|---|---:|---|
| GET | `/Switchfy/test/live-totals` | 200 | `capped`, `senders`, `terminations`, `countries`, `messages`, `ranges`, `countries_total`, `success` |
| GET | `/Switchfy/test/live-history` | 200 | `success`, `records` |
| GET | `/Switchfy/test/termination-meta` | 200 | `success`, `terms` |

The captured requests include a query parameter named `limit` for live-totals/live-history, and `ids` for termination-meta. Values and session headers are intentionally not copied into this document. These browser-session observations are not used by the current API-key flow.

Some dashboard requests include a header named `X-CSRF-Token`; this is evidence of a CSRF-related header, not evidence about how the token is obtained, scoped, or refreshed. Do not hardcode its value or reuse it from HAR.

### How to capture the missing login flow

To identify the actual login process, start a **new** DevTools Network recording at the Augestel login page before entering credentials, enable Preserve log, then sign in normally. The capture needs to show the request method/path and response status for the login attempt. Do not send a raw HAR if it contains passwords, session cookies, CSRF values, authorization headers, or tokens; provide a redacted screenshot of the request metadata instead.

The current integration uses the documented API-key flow, not the browser password form. The bot does not collect website passwords, cookies, session tokens, or challenge payloads.


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

This capture does not show Add Number, Export, or Return All being triggered. The documented Bearer API-key scheme is confirmed only for the `/api/v1/iprn` API endpoints, not for these website routes. The custom write adapter uses the user's Bearer key only as an opt-in attempt on the same Augestel host, and stops if the fresh page/metadata requests are redirected or rejected. It does not replay tokens from HAR or bypass challenge/anti-abuse controls.


## Add Number draft validation (2026-10-14)

The bot now accepts a local draft command:

```text
/addnumber <termination_id> <termination_term_id> <count> <sort_type>
```

The four business fields are based on the observed browser form submission. The command validates identifiers, positive count, and safe sort-type syntax; a conservative local draft ceiling of 1,000 prevents accidental oversized drafts. This ceiling is an application safeguard, not an Augestel limit.

A valid draft is recorded as a confirmation request and presents an explicit confirm/cancel keyboard. On confirmation, the adapter first makes a fresh GET to the live numbers page to obtain the current CSRF token. It then requests fresh termination metadata to verify the selected term, available count, per-request limit, remaining termination limit, supported sort type, and dynamic `request_token`. Only after those checks does it POST the form fields if `AUGESTEL_CUSTOM_WRITE_ENABLED=true`. Tokens are read fresh at runtime; values are never copied from HAR. The adapter does not solve or bypass any challenge. If the page redirects to login or CSRF protection rejects the request, it stops safely. Since these are website routes, successful live execution has not yet been verified.


## Bearer API client foundation (2026-10-14)

The user-provided Authentication section documents Bearer token authentication: `Authorization: Bearer YOUR_API_KEY`. The read-only JSON GET helper receives the calling Telegram user's key in memory as a `SecretStr`. Keys are encrypted before being stored in the database; the Fernet master key `API_KEY_ENCRYPTION_KEY` is supplied by the operator separately.

The documented Base URL is now configured as `https://augestel.com/api/v1/iprn`. The My Numbers resource endpoint is now documented and implemented. Verify endpoint paths and request/response schemas for any additional operation before enabling those features. Do not use `/Switchfy/client/numbers/request`, `/Switchfy/client/numbers/export`, or `/Switchfy/client/numbers/bulk-return-all` in the API client merely because they were seen in browser HAR files.

Example local configuration (do not commit `.env`):

```dotenv
AUGESTEL_API_BASE_URL=https://augestel.com/api/v1/iprn
API_KEY_ENCRYPTION_KEY=put_generated_fernet_key_here
AUGESTEL_INTEGRATION_ENABLED=true
```

Generate the Fernet key using `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Back up this master key securely; if it is lost or changed, already stored API keys cannot be decrypted.

The API Base URL is taken directly from the documentation supplied by the user. `GET /numbers` is implemented via `AugestelClient.list_numbers()` and exposed in **My Numbers** and `/numbers`. Add Number and Return All have separate guarded website-route adapters documented below; export download remains a placeholder pending a confirmed response format.

**Key rotation:** the earlier screenshot showed an API key visibly. Treat that key as exposed and regenerate it in the Augestel dashboard before using any key locally.


## My Numbers endpoint (2026-10-14)

The user-provided official endpoint page documents:

- Method: `GET`
- Relative endpoint: `/numbers`
- Full URL: `https://augestel.com/api/v1/iprn/numbers`
- Authentication: `Authorization: Bearer YOUR_API_KEY`
- Accept header: `application/json`
- Query parameters:
  - `page` (integer, optional, default 1)
  - `per_page` (integer, optional, default 20, maximum 100)
  - `range_name` (string, optional filter)

The documented response object has `success`, `data` (array), and `pagination` keys. Number records contain `number`, `range_name`, `a2p_rate`, `portal_limit_a2p`, `last_message_at`, and `assigned_at`. Pagination contains `current_page`, `per_page`, `total`, and `last_page`.

The application now uses `AugestelClient.list_numbers()` and surfaces this read-only data through **📱 My Numbers** and `/numbers`, with next/previous page buttons. Command `/numbers 2` can open page 2. The client checks basic response structure before the bot formats any values for Telegram; displayed provider text is HTML-escaped. The API key is not stored in operation history.

The feature remains disabled by default. Set `API_KEY_ENCRYPTION_KEY` in the operator environment, regenerate any API key previously visible in the screenshot, and set `AUGESTEL_INTEGRATION_ENABLED=true` only when intentionally allowing the documented read-only API. Each user then connects their regenerated key through `/connect` in the private chat. The CI tests use mocked HTTP responses; no live request was sent from the development process.

Add Number and Return All are implemented as optional custom website-route attempts, but remain disabled by default and may fail if Bearer auth is not accepted. Export download remains disabled pending its response contract.


## Per-user API key intake and storage (2026-10-14)

The application no longer uses a single global `AUGESTEL_API_KEY`. Each Telegram user connects their own API key using `/connect` in the private bot chat:

1. The bot checks that the integration is enabled and that `API_KEY_ENCRYPTION_KEY` is correctly configured before prompting the user.
2. The user is told not to share the key with people or groups and to submit it only for the private connection flow.
3. The bot accepts the key as a text message, attempts to delete that source message immediately, and never echoes it.
4. The key is validated with the official read-only `GET /numbers?page=1&per_page=1` endpoint.
5. On successful validation, the key is encrypted with Fernet and saved to that user's `website_accounts.api_key_encrypted` field.
6. My Numbers decrypts only the requesting user's key at runtime. The key value is not written to operation history.
7. `/disconnect` removes the encrypted key from the database.

Message deletion is best-effort, not a guarantee. API keys should only be sent in private chat; users should regenerate any key exposed in screenshots, groups, logs, or public repositories.

The operator must generate `API_KEY_ENCRYPTION_KEY` once and back it up securely. Do not change it casually: existing key ciphertext cannot be decrypted after the master key is lost or replaced. Existing database schemas are updated with an `api_key_encrypted` column without dropping existing data.

The FSM uses in-memory storage, so an interrupted connect prompt can be lost on bot restart; the user can simply start `/connect` again.


## Custom Add Number and Return All adapters (2026-10-14)

The provider's published API documentation supplied in this conversation does not list write endpoints. The user reported that Augestel support said these flows may be implemented separately. The following website routes were observed in user-provided HAR files:

- Add Number: `POST https://augestel.com/Switchfy/client/numbers/request`
- Return All: `POST https://augestel.com/Switchfy/client/numbers/bulk-return-all`

These remain **observed website routes, not documented public API endpoints**. The adapter is opt-in via `AUGESTEL_CUSTOM_WRITE_ENABLED=false` (default). It sends the connected Telegram user's own API key in an `Authorization: Bearer` header to the same HTTPS origin; that use against website routes remains unverified until tested on an account the user controls. For each operation it makes a fresh GET to `/Switchfy/client/numbers` and extracts the current CSRF token from that response. Add Number then makes a fresh GET to `/Switchfy/client/numbers/terminations?termination_id=...`, validates the chosen numeric termination/term IDs and limits, and uses the returned `request_token`. The subsequent POST sends `_token` plus that fresh `request_token`; Return All sends `_token`. No token is copied from HAR and no redirect is followed. If API-key authorization is not supported on the web routes, the initial GET is expected to fail or redirect and no write request is sent.

The bot validates Add Number input, previews the target/count, and requires a confirm click. Return All first reads the current count via the documented `GET /numbers`, previews that count, and rechecks the count at confirmation time; if the count changed, a fresh confirmation is required. Both flows clear their pending confirmation state before sending a POST so repeated button clicks don't issue another request.

Because POSTs can be processed before a redirect, timeout, 5xx, or connection failure, the client marks those responses as `outcome_unknown`. The bot never retries automatically: users must check `/numbers` and the Augestel portal before deciding what to do next. A 401/403 is reported as lack of authorization; a 419 explicitly says browser/CSRF protection is not bypassed. If these website routes require a browser session beyond a page returned to the Bearer API key, the API key alone will not make them work; obtain a supported mechanism from Augestel rather than copying browser tokens from HAR or bypassing challenges.

To attempt these custom routes in a local test environment only, the operator must deliberately set both:

```dotenv
AUGESTEL_INTEGRATION_ENABLED=true
AUGESTEL_CUSTOM_WRITE_ENABLED=true
```

Use only an account you control, double-check the account and count before confirming Return All, and do not run destructive tests against an account with numbers you need to keep.


### Termination discovery command

The bot exposes `/terminations` for private-chat users with a connected API key. It fetches fresh website page/metadata through the guarded custom-write adapter and displays the termination numeric ID, current available count, max-per-request, allowed `number_sort_type`, and numeric term IDs. It intentionally omits `request_token` from its response. Users should use these returned IDs/allowed sort value when invoking `/addnumber`. This discovery route is gated by both integration flags because it calls an observed website route, not the documented public API.
