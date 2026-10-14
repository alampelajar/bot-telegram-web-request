"""Augestel integration boundary.

Observed browser routes are not assumed to be a supported public API. Enable
operations only after confirming the permitted authentication method and contract.
"""
from dataclasses import dataclass
from typing import Any

from app.config import get_settings


class AugestelIntegrationDisabled(RuntimeError):
    pass


class AugestelIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AugestelClient:
    base_url: str

    @classmethod
    def from_settings(cls) -> "AugestelClient":
        settings = get_settings()
        return cls(base_url=settings.augestel_base_url.rstrip("/"))

    def _ensure_enabled(self) -> None:
        if not get_settings().augestel_integration_enabled:
            raise AugestelIntegrationDisabled(
                "Augestel integration is disabled until an approved authentication method is configured."
            )

    async def get_export(self) -> bytes:
        self._ensure_enabled()
        raise AugestelIntegrationError(
            "Export adapter is not implemented; verify approved authentication and API contract."
        )

    async def add_numbers(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_enabled()
        raise AugestelIntegrationError(
            "Add Number adapter is not implemented; verify the provider contract first."
        )

    async def return_all(self) -> dict[str, Any]:
        self._ensure_enabled()
        raise AugestelIntegrationError(
            "Return All adapter is not implemented; verify the provider contract first."
        )
