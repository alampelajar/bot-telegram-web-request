# Product Requirements Document — Automatic Web Controller

Version: 1.0  
Status: Development baseline  
Platform: Telegram Bot  
Website: Augestel  
Runtime: Python 3.11

## 1. Product summary

Automatic Web Controller lets an authorized user manage their own Augestel account through Telegram. The MVP focuses on Add Number, Download Numbers, and Return All, supported by account connection state, activity history, and access controls.

## 2. MVP scope

| Feature | Priority | Requirements |
|---|---|---|
| Connect Account | P0 | Securely establish an authorized account connection |
| Add Number | P0 | Select termination, payment term, and quantity; show confirmation; report actual result |
| Download Numbers | P0 | Retrieve and validate XLSX export; send it to the account owner |
| Return All | P0 | Display scope/count and require explicit confirmation |
| Account Status | P0 | Show connection state without exposing secrets |
| Operation History | P0 | Store operation type, timestamp, status, and safe summary |
| Access Control | P0 | Restrict operations to authorized Telegram users |
| Error Handling | P0 | Handle authentication errors, timeouts, and uncertain results |

## 3. Observed Augestel pages and routes

Observed from user-provided dashboard screenshots and HAR files:

- EDR History page: `/Switchfy/test/edr-history`
- My Numbers page: `/Switchfy/client/numbers`
- Add Number route: `POST /Switchfy/client/numbers/request`
- XLSX export route: `GET /Switchfy/client/numbers/export`
- Return All route: `POST /Switchfy/client/numbers/bulk-return-all`

These are observed website routes, not confirmation that Augestel offers a supported public API. Before implementation, confirm that the chosen authentication and integration method is permitted by Augestel. Do not infer or hardcode session cookies, CSRF tokens, or request tokens from HAR files.

## 4. Add Number workflow

1. Confirm that the user is connected to their own authorized account.
2. Retrieve termination choices using the approved integration method.
3. User selects a termination and payment term.
4. User enters a quantity.
5. Validate quantity, availability, rate, and cost where supported by verified source data.
6. Display a confirmation summary.
7. Execute only after confirmation.
8. Verify the response and report success, partial failure, failure, or unknown outcome accurately.

## 5. Download workflow

1. Validate account ownership and connection.
2. Request the export through the approved integration method.
3. Validate content type and file signature.
4. Send the XLSX to the requesting account owner.
5. Delete temporary files according to configured retention.

Never report success if the request returns an error page or invalid file.

## 6. Return All workflow

1. Fetch/verify current scope and count where possible.
2. Explain that every number within the operation's scope can be returned.
3. Require explicit confirmation.
4. Execute only once after confirmation.
5. Verify the outcome.
6. On timeout, mark the result unknown and verify server state before retrying. Never blindly retry a bulk return.

## 7. Architecture and stack

- Python 3.11
- aiogram 3
- httpx integration adapter
- PostgreSQL and SQLAlchemy
- Alembic migrations
- Docker Compose
- pytest

Suggested logical modules: Telegram handlers, application services, Augestel adapter, database models/repositories, settings, and worker jobs if operations become long-running.

## 8. Security

- Isolate every user’s account data.
- Never store passwords in plaintext or log cookies/tokens.
- Keep secrets in environment/secret management; never commit .env or HAR files.
- Verify authorization before every operation.
- Restrict admin actions to configured Telegram IDs.
- Add rate limits, structured error handling, and safe temporary-file cleanup.
- Obtain authorization for the integration method before production use.

## 9. Acceptance criteria

- Unauthorized users cannot perform operations.
- Account connection state is shown accurately.
- Add Number requires confirmation and reports verified results.
- Download sends a validated XLSX from the connected account.
- Return All requires explicit confirmation and is not blindly retried.
- Users cannot read or mutate another user’s account data.
- Sensitive credentials never appear in logs.
- Errors and uncertain outcomes are reported truthfully.
- Unit and integration tests cover safety guards and failure paths.

## 10. Implementation notes / open decisions

- Provider-supported authentication method and permissions.
- Actual request and response schemas.
- CSRF/request token lifecycle, where applicable.
- Provider rate limits and operation limits.
- Deployment host and target user count.
- Final data retention period.

The adapter must remain disabled until the integration contract and permitted authentication mechanism are verified.
