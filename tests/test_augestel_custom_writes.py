import httpx
import pytest
from pydantic import SecretStr

import app.integrations.augestel as augestel
from app.config import Settings
from app.integrations.augestel import (
    AugestelClient,
    AugestelIntegrationDisabled,
    AugestelIntegrationError,
    AugestelOperationOutcomeUnknown,
)


def _custom_write_settings(*, enabled: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        augestel_integration_enabled=True,
        augestel_custom_write_enabled=enabled,
        augestel_api_base_url="https://augestel.com/api/v1/iprn",
        augestel_base_url="https://augestel.com",
    )


@pytest.mark.asyncio
async def test_custom_add_number_sends_only_business_fields_with_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"success": True},
        )

    settings = _custom_write_settings()
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=SecretStr("test-only-key"),
        transport=httpx.MockTransport(handler),
    )

    result = await client.add_numbers(
        {
            "termination_id": "term_123",
            "termination_term_id": "term_456",
            "count": 5,
            "sort_type": "asc",
        }
    )

    assert result["success"] is True
    assert len(seen) == 1
    assert seen[0].method == "POST"
    assert seen[0].url.host == "augestel.com"
    assert seen[0].url.path == "/Switchfy/client/numbers/request"
    assert seen[0].headers["Authorization"] == "Bearer test-only-key"
    assert b"termination_id=term_123" in seen[0].content
    assert b"termination_term_id=term_456" in seen[0].content
    assert b"count=5" in seen[0].content
    assert b"sort_type=asc" in seen[0].content
    assert b"_token" not in seen[0].content
    assert b"request_token" not in seen[0].content
    assert b"test-only-key" not in seen[0].content


@pytest.mark.asyncio
async def test_custom_return_all_is_disabled_by_default_and_sends_no_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"success": True})

    settings = _custom_write_settings(enabled=False)
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=SecretStr("test-only-key"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AugestelIntegrationDisabled, match="AUGESTEL_CUSTOM_WRITE_ENABLED"):
        await client.return_all()
    assert called is False


@pytest.mark.asyncio
async def test_custom_return_all_uses_observed_route_when_opted_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"success": True, "message": "ok"},
        )

    settings = _custom_write_settings()
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=SecretStr("test-only-key"),
        transport=httpx.MockTransport(handler),
    )

    result = await client.return_all()

    assert result["success"] is True
    assert len(seen) == 1
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/Switchfy/client/numbers/bulk-return-all"
    assert seen[0].headers["Authorization"] == "Bearer test-only-key"


@pytest.mark.asyncio
async def test_custom_write_redirect_has_unknown_outcome_and_is_not_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://augestel.com/Switchfy/login"})

    settings = _custom_write_settings()
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=SecretStr("test-only-key"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AugestelOperationOutcomeUnknown, match="result is unknown"):
        await client.return_all()
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_custom_write_csrf_rejection_is_not_bypassed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _custom_write_settings()
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=SecretStr("test-only-key"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(419, json={"message": "CSRF token mismatch"})
        ),
    )

    with pytest.raises(AugestelIntegrationError, match="does not bypass"):
        await client.return_all()


@pytest.mark.asyncio
async def test_custom_add_number_rejects_invalid_payload_without_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"success": True})

    settings = _custom_write_settings()
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=SecretStr("test-only-key"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AugestelIntegrationError, match="count"):
        await client.add_numbers(
            {
                "termination_id": "term_123",
                "termination_term_id": "term_456",
                "count": 0,
                "sort_type": "asc",
            }
        )
    assert called is False
