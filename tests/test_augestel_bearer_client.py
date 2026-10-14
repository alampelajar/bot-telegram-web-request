import httpx
import pytest
from pydantic import SecretStr

import app.integrations.augestel as augestel
from app.config import Settings
from app.integrations.augestel import (
    AugestelClient,
    AugestelIntegrationDisabled,
    AugestelIntegrationError,
)


@pytest.mark.asyncio
async def test_export_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(augestel_integration_enabled=False)
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url="https://augestel.com/v1",
        api_key=SecretStr("test-key"),
    )
    with pytest.raises(AugestelIntegrationDisabled):
        await client.get_export()


@pytest.mark.asyncio
async def test_get_json_sends_bearer_auth_and_parses_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"success": True, "records": []},
        )

    settings = Settings(
        augestel_integration_enabled=True,
        augestel_api_base_url="https://augestel.com/v1",
        augestel_api_key=SecretStr("test-only-token"),
    )
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=settings.augestel_api_key,
        transport=httpx.MockTransport(handler),
    )

    result = await client.get_json("/numbers", params={"limit": 10})

    assert result == {"success": True, "records": []}
    assert len(seen) == 1
    assert seen[0].url.path == "/v1/numbers"
    assert seen[0].url.params["limit"] == "10"
    assert seen[0].headers["Authorization"] == "Bearer test-only-token"
    assert seen[0].headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_get_json_requires_enabled_integration_and_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        augestel_integration_enabled=True,
        augestel_api_base_url="https://augestel.com/v1",
        augestel_api_key=SecretStr(""),
    )
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(base_url=settings.augestel_api_base_url, api_key=settings.augestel_api_key)

    with pytest.raises(AugestelIntegrationDisabled, match="AUGESTEL_API_KEY"):
        await client.get_json("/numbers")


@pytest.mark.asyncio
async def test_redirect_is_rejected_without_following(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://attacker.example/collect"})

    settings = Settings(
        augestel_integration_enabled=True,
        augestel_api_base_url="https://augestel.com/v1",
        augestel_api_key=SecretStr("test-only-token"),
    )
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=settings.augestel_api_key,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AugestelIntegrationError, match="redirect"):
        await client.get_json("/numbers")

    assert len(seen) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url",
    [
        "http://augestel.com/api",
        "https://augestel.com.attacker.example/api",
        "https://attacker.example/api",
        "https://user:password@augestel.com/api",
        "https://augestel.com:8443/api",
    ],
)
async def test_untrusted_base_url_is_rejected(
    monkeypatch: pytest.MonkeyPatch, base_url: str
) -> None:
    settings = Settings(
        augestel_integration_enabled=True,
        augestel_api_base_url=base_url,
        augestel_api_key=SecretStr("test-only-token"),
    )
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=base_url,
        api_key=settings.augestel_api_key,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )

    with pytest.raises(AugestelIntegrationError, match="HTTPS URL"):
        await client.get_json("/numbers")


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["https://evil.example/x", "//evil.example/x", "/../login", "/a/../login"])
async def test_unsafe_api_path_is_rejected(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    settings = Settings(
        augestel_integration_enabled=True,
        augestel_api_base_url="https://augestel.com/v1",
        augestel_api_key=SecretStr("test-only-token"),
    )
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=settings.augestel_api_key,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )

    with pytest.raises(AugestelIntegrationError, match="API path"):
        await client.get_json(path)


@pytest.mark.asyncio
async def test_non_json_response_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        augestel_integration_enabled=True,
        augestel_api_base_url="https://augestel.com/v1",
        augestel_api_key=SecretStr("test-only-token"),
    )
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=settings.augestel_api_key,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="<html>login</html>")
        ),
    )

    with pytest.raises(AugestelIntegrationError, match="non-JSON"):
        await client.get_json("/numbers")
