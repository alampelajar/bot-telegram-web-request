"""Safe bearer-token client foundation for Augestel's documented REST API.

Only read-only JSON GET requests are implemented here. Endpoint paths must come
from Augestel's API documentation; browser-only routes are not assumed to be
public API routes. The integration stays disabled unless explicitly enabled.
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
    def from_settings(cls) -> "AugestelClient":
        settings = get_settings()
        return cls(
            base_url=settings.augestel_api_base_url.rstrip("/"),
            api_key=settings.augestel_api_key,
        )

    def _ensure_enabled(self) -> str:
        settings = get_settings()
        if not settings.augestel_integration_enabled:
            raise AugestelIntegrationDisabled(
                "Augestel API integration is disabled. Enable it only after the API base URL "
                "and required endpoint contracts have been verified."
            )

        token = self.api_key.get_secret_value().strip() if self.api_key else ""
        if not token:
            raise AugestelIntegrationDisabled(
                "AUGESTEL_API_KEY is not configured. Store the API key in the local .env file."
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
        """Make a read-only GET with Authorization: Bearer <API key>.

        Redirects are disabled so the Authorization header cannot be forwarded
        to a redirect target. Error text intentionally excludes response bodies,
        URLs, and credentials because provider responses can contain sensitive data.
        """
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

    async def get_export(self) -> bytes:
        self._ensure_enabled()
        raise AugestelIntegrationError(
            "Export adapter is not implemented; verify the documented API endpoint and response format."
        )

    async def add_numbers(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_enabled()
        raise AugestelIntegrationError(
            "Add Number submission is not implemented; verify the documented API payload first."
        )

    async def return_all(self) -> dict[str, Any]:
        self._ensure_enabled()
        raise AugestelIntegrationError(
            "Return All is not implemented; verify the documented API endpoint and confirmation semantics."
        )
