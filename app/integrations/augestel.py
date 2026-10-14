"""Safe bearer-token client for Augestel's documented REST API.

Read-only endpoint support is based on the user-provided API documentation.
Write operations remain guarded until their documented contracts are provided.
"""
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from app.config import get_settings


class AugestelIntegrationDisabled(RuntimeError):
    pass


class AugestelIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AugestelClient:
    base_url: str
    api_key: SecretStr | None = None
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_settings(cls, api_key: SecretStr | None = None) -> "AugestelClient":
        """Build a client for one specific user-provided API key.

        No process-wide API key is configured: callers must supply the key
        belonging to the Telegram user whose account they are accessing.
        """
        settings = get_settings()
        return cls(
            base_url=settings.augestel_api_base_url.rstrip("/"),
            api_key=api_key,
        )

    def _ensure_enabled(self) -> str:
        settings = get_settings()
        if not settings.augestel_integration_enabled:
            raise AugestelIntegrationDisabled(
                "Augestel API integration is disabled. Enable it only after the documented "
                "API endpoints are verified."
            )

        token = self.api_key.get_secret_value().strip() if self.api_key else ""
        if not token:
            raise AugestelIntegrationDisabled(
                "No API key is connected to this user. Connect an Augestel API key in a private chat first."
            )
        return token

    def _validated_base_url(self) -> str:
        parsed = urlsplit(self.base_url)
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not hostname
            or not (hostname == "augestel.com" or hostname.endswith(".augestel.com"))
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.port not in (None, 443)
        ):
            raise AugestelIntegrationError(
                "AUGESTEL_API_BASE_URL must be an HTTPS URL on augestel.com, copied from "
                "the provider's API documentation."
            )
        return self.base_url.rstrip("/")

    @staticmethod
    def _validated_path(path: str) -> str:
        parsed = urlsplit(path)
        if (
            not path.startswith("/")
            or path.startswith("//")
            or parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or "\\" in path
            or any(part == ".." for part in parsed.path.split("/"))
        ):
            raise AugestelIntegrationError(
                "API path must be a documented path beginning with one slash; pass query values "
                "through the params argument."
            )
        return path

    async def get_json(
        self,
        path: str,
        *,
        params: dict[str, str | int | bool] | None = None,
    ) -> Any:
        """Make a read-only GET with Authorization: Bearer <API key>."""
        token = self._ensure_enabled()
        base_url = self._validated_base_url()
        safe_path = self._validated_path(path)
        url = f"{base_url}{safe_path}"

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=5.0),
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                )
        except httpx.TimeoutException as exc:
            raise AugestelIntegrationError("Augestel API request timed out.") from exc
        except httpx.RequestError as exc:
            raise AugestelIntegrationError("Unable to connect to Augestel API.") from exc

        if 300 <= response.status_code < 400:
            raise AugestelIntegrationError(
                "Augestel API returned a redirect; redirects are blocked for credential safety."
            )
        if response.status_code == 401:
            raise AugestelIntegrationError("Augestel API rejected the API key (HTTP 401).")
        if response.status_code == 403:
            raise AugestelIntegrationError(
                "The API key does not have permission for this operation (HTTP 403)."
            )
        if response.status_code == 404:
            raise AugestelIntegrationError(
                "Augestel API endpoint was not found (HTTP 404); verify the documented base URL/path."
            )
        if response.status_code == 429:
            raise AugestelIntegrationError(
                "Augestel API rate limit reached (HTTP 429); wait before retrying."
            )
        if response.status_code >= 500:
            raise AugestelIntegrationError(
                f"Augestel API service error (HTTP {response.status_code})."
            )
        if response.is_error:
            raise AugestelIntegrationError(
                f"Augestel API request failed (HTTP {response.status_code})."
            )

        content_type = response.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            raise AugestelIntegrationError(
                "Augestel API returned a non-JSON response; verify the documented API URL."
            )
        try:
            return response.json()
        except ValueError as exc:
            raise AugestelIntegrationError("Augestel API returned invalid JSON.") from exc

    async def list_numbers(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        range_name: str | None = None,
    ) -> dict[str, Any]:
        """Fetch the documented read-only GET /numbers resource."""
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise AugestelIntegrationError("page must be an integer greater than or equal to 1.")
        if (
            isinstance(per_page, bool)
            or not isinstance(per_page, int)
            or not 1 <= per_page <= 100
        ):
            raise AugestelIntegrationError("per_page must be an integer between 1 and 100.")

        params: dict[str, str | int | bool] = {"page": page, "per_page": per_page}
        if range_name is not None and range_name.strip():
            params["range_name"] = range_name.strip()[:100]

        payload = await self.get_json("/numbers", params=params)
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise AugestelIntegrationError("Augestel API returned an unsuccessful numbers response.")

        records = payload.get("data")
        pagination = payload.get("pagination")
        if not isinstance(records, list) or not isinstance(pagination, dict):
            raise AugestelIntegrationError("Augestel API numbers response has an unexpected schema.")

        validated_records: list[dict[str, Any]] = []
        for item in records:
            if not isinstance(item, dict):
                raise AugestelIntegrationError("Augestel API returned an invalid number record.")
            number = item.get("number")
            range_label = item.get("range_name")
            if not isinstance(number, str) or not isinstance(range_label, str):
                raise AugestelIntegrationError("Augestel API returned an invalid number record.")
            validated_records.append(item)

        for key in ("current_page", "per_page", "total", "last_page"):
            value = pagination.get(key)
            minimum = 1 if key in ("current_page", "per_page") else 0
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < minimum
            ):
                raise AugestelIntegrationError("Augestel API returned invalid pagination metadata.")

        return {
            "success": True,
            "data": validated_records,
            "pagination": pagination,
        }

    async def get_export(self) -> bytes:
        self._ensure_enabled()
        raise AugestelIntegrationError(
            "Export adapter is not implemented; verify the documented API endpoint and response format."
        )

    def _ensure_custom_writes_enabled(self) -> str:
        token = self._ensure_enabled()
        if not get_settings().augestel_custom_write_enabled:
            raise AugestelIntegrationDisabled(
                "Custom Add Number/Return All requests are disabled. The operator must explicitly "
                "enable AUGESTEL_CUSTOM_WRITE_ENABLED after reviewing the observed website routes."
            )
        return token

    async def _post_website_form(
        self,
        path: str,
        *,
        data: dict[str, str | int],
    ) -> dict[str, Any]:
        """Attempt a user-authorized website action with Bearer auth only.

        These two routes were observed in the user's HAR and are not documented API v1
        endpoints. No browser cookie, CSRF token, or request_token is invented/replayed.
        If Augestel requires a browser session or challenge, this fails closed.
        """
        token = self._ensure_custom_writes_enabled()
        allowed_paths = {
            "/Switchfy/client/numbers/request",
            "/Switchfy/client/numbers/bulk-return-all",
        }
        if path not in allowed_paths:
            raise AugestelIntegrationError("Website write path is not in the explicit allowlist.")

        settings = get_settings()
        website_base = settings.augestel_base_url.rstrip("/")
        parsed = urlsplit(website_base)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "augestel.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.port not in (None, 443)
        ):
            raise AugestelIntegrationError(
                "AUGESTEL_BASE_URL must be exactly https://augestel.com for these observed routes."
            )

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(20.0, connect=5.0),
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    f"{website_base}{path}",
                    data=data,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            # The server may have processed a POST before the connection failed.
            raise AugestelOperationOutcomeUnknown(
                "The Augestel write request ended without a confirmed response. Check My Numbers "
                "before retrying; the bot will not retry automatically."
            ) from exc

        if 300 <= response.status_code < 400:
            # A website redirect can follow a successful form submission. Never retry blindly.
            raise AugestelOperationOutcomeUnknown(
                "Augestel returned a redirect after the write request. Its result is unknown; "
                "check My Numbers in the portal/bot before considering another attempt. "
                "Redirects were not followed."
            )
        if response.status_code in (401, 403):
            raise AugestelIntegrationError(
                f"Augestel did not authorize the custom website write request (HTTP {response.status_code}). "
                "The API key may be limited to the documented API v1 routes."
            )
        if response.status_code == 419:
            raise AugestelIntegrationError(
                "The website route requires a CSRF/browser session. This bot does not bypass that protection."
            )
        if response.status_code == 422:
            raise AugestelIntegrationError(
                "Augestel rejected the custom write form (HTTP 422). Required form fields or a supported "
                "write contract may be missing; no automatic retry was made."
            )
        if response.status_code == 429:
            raise AugestelIntegrationError(
                "Augestel rate-limited the custom write request (HTTP 429). Check the account before retrying."
            )
        if response.status_code >= 500:
            raise AugestelOperationOutcomeUnknown(
                f"Augestel returned HTTP {response.status_code} after a write request. "
                "Check My Numbers before retrying; the bot will not retry automatically."
            )
        if response.is_error:
            raise AugestelIntegrationError(
                f"Augestel rejected the custom write request (HTTP {response.status_code})."
            )

        if "application/json" not in response.headers.get("content-type", "").lower():
            raise AugestelOperationOutcomeUnknown(
                "Augestel returned a non-JSON response to the write request. The result is unknown; "
                "check My Numbers before retrying."
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise AugestelOperationOutcomeUnknown(
                "Augestel returned invalid JSON after a write request. Check My Numbers before retrying."
            ) from exc
        if not isinstance(payload, dict):
            raise AugestelOperationOutcomeUnknown(
                "Augestel returned an unexpected write response. Check My Numbers before retrying."
            )
        if payload.get("success") is not True:
            # Do not send raw response details to Telegram or activity logs.
            raise AugestelIntegrationError(
                "Augestel did not confirm that the operation succeeded. Check My Numbers before retrying."
            )
        return payload

    async def add_numbers(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Submit the observed Add Number form fields after explicit user confirmation.

        Only the business fields are sent. CSRF/request tokens are deliberately not
        scraped, fabricated, or replayed; if the route requires them it must fail safely.
        """
        termination_id = payload.get("termination_id")
        termination_term_id = payload.get("termination_term_id")
        count = payload.get("count")
        sort_type = payload.get("sort_type")
        if not isinstance(termination_id, str) or not termination_id.strip() or len(termination_id) > 100:
            raise AugestelIntegrationError("termination_id is required and must be at most 100 characters.")
        if not isinstance(termination_term_id, str) or not termination_term_id.strip() or len(termination_term_id) > 100:
            raise AugestelIntegrationError("termination_term_id is required and must be at most 100 characters.")
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 1000:
            raise AugestelIntegrationError("count must be an integer between 1 and 1000.")
        if not isinstance(sort_type, str) or not sort_type.strip() or len(sort_type) > 32:
            raise AugestelIntegrationError("sort_type is required and must be at most 32 characters.")
        return await self._post_website_form(
            "/Switchfy/client/numbers/request",
            data={
                "termination_id": termination_id.strip(),
                "termination_term_id": termination_term_id.strip(),
                "count": count,
                "sort_type": sort_type.strip(),
            },
        )

    async def return_all(self) -> dict[str, Any]:
        """Return all assigned numbers only after an explicit confirmation."""
        return await self._post_website_form(
            "/Switchfy/client/numbers/bulk-return-all",
            data={},
        )


class AugestelOperationOutcomeUnknown(AugestelIntegrationError):
    """A write request may have been processed but has no trustworthy success response."""
