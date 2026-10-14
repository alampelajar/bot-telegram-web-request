# Augestel integration notes

Observed browser request paths from user-provided HAR files:

- Add Number: `POST /Switchfy/client/numbers/request`
- Export: `GET /Switchfy/client/numbers/export`
- Return All: `POST /Switchfy/client/numbers/bulk-return-all`

These are observed website routes, not confirmation of a supported public API.

Before implementing requests:
1. Confirm Augestel permits this integration.
2. Confirm the supported authentication method and account isolation strategy.
3. Identify how CSRF/request tokens are obtained, scoped, and refreshed without logging or hardcoding them.
4. Verify request payloads and response schemas using non-destructive operations first.
5. Require explicit confirmation for Add Number and Return All.
6. Never blindly retry a timed-out Return All; determine whether the prior operation completed.
7. Never commit HAR files, cookies, bearer tokens, passwords, or export data.

The adapter intentionally raises an error rather than sending guessed requests until these are confirmed.
