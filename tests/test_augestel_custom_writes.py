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


def _website_page_response() -> httpx.Response:
    return httpx.Response(
        200,
        headers={
            "content-type": "text/html; charset=utf-8",
            "set-cookie": "awc_test_session=fresh-session; Path=/; Secure; HttpOnly",
        },
        text='<html><head><meta name="csrf-token" content="fresh-csrf-token"></head></html>',
    )


def _termination_metadata_response() -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "application/json"},
        json={
            "success": True,
            "terminations": [
                {
                    "id": 12345,
                    "name": "Example termination",
                    "available_count": 20,
                    "max_per_request": 10,
                    "number_sort_type": "random",
                    "current_from_termination": 0,
                    "limit_per_termination": 20,
                    "request_token": "fresh-request-token-from-metadata",
                    "terms": [
                        {"id": 123456, "term": "7/1", "a2p_rate": 0.01, "is_default": True}
                    ],
                }
            ],
            "total": 1,
            "truncated": False,
        },
    )


@pytest.mark.asyncio
async def test_custom_add_number_uses_fresh_csrf_and_request_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET" and request.url.path == "/Switchfy/client/numbers":
            return _website_page_response()
        if request.method == "GET" and request.url.path == "/Switchfy/client/numbers/terminations":
            return _termination_metadata_response()
        if request.method == "POST" and request.url.path == "/Switchfy/client/numbers/request":
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"success": True, "message": "ok", "numbers": []},
            )
        return httpx.Response(404, json={"success": False})

    settings = _custom_write_settings()
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=SecretStr("test-only-key"),
        transport=httpx.MockTransport(handler),
    )

    result = await client.add_numbers(
        {
            "termination_id": "12345",
            "termination_term_id": "123456",
            "count": 5,
            "sort_type": "random",
        }
    )

    assert result["success"] is True
    assert [request.method for request in seen] == ["GET", "GET", "POST"]
    assert seen[0].url.path == "/Switchfy/client/numbers"
    assert seen[0].headers["Authorization"] == "Bearer test-only-key"
    assert seen[1].url.path == "/Switchfy/client/numbers/terminations"
    assert seen[1].url.params["termination_id"] == "12345"
    assert seen[1].headers["X-CSRF-Token"] == "fresh-csrf-token"
    assert seen[2].url.path == "/Switchfy/client/numbers/request"
    assert seen[2].headers["Authorization"] == "Bearer test-only-key"
    assert seen[2].headers["X-CSRF-Token"] == "fresh-csrf-token"
    assert "awc_test_session=fresh-session" in seen[1].headers.get("Cookie", "")
    assert "awc_test_session=fresh-session" in seen[2].headers.get("Cookie", "")

    from urllib.parse import parse_qs

    form = parse_qs(seen[2].content.decode("utf-8"))
    assert form["_token"] == ["fresh-csrf-token"]
    assert form["termination_id"] == ["12345"]
    assert form["termination_term_id"] == ["123456"]
    assert form["count"] == ["5"]
    assert form["sort_type"] == ["random"]
    assert form["request_token"] == ["fresh-request-token-from-metadata"]
    assert "test-only-key" not in seen[2].content.decode("utf-8")


@pytest.mark.asyncio
async def test_custom_writes_are_disabled_by_default_and_send_no_request(
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
async def test_custom_return_all_uses_fresh_csrf_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET" and request.url.path == "/Switchfy/client/numbers":
            return _website_page_response()
        if request.method == "POST" and request.url.path == "/Switchfy/client/numbers/bulk-return-all":
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"success": True, "message": "ok"},
            )
        return httpx.Response(404, json={"success": False})

    settings = _custom_write_settings()
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=SecretStr("test-only-key"),
        transport=httpx.MockTransport(handler),
    )

    result = await client.return_all()

    assert result["success"] is True
    assert [request.method for request in seen] == ["GET", "POST"]
    assert seen[1].url.path == "/Switchfy/client/numbers/bulk-return-all"
    assert seen[1].headers["Authorization"] == "Bearer test-only-key"
    assert seen[1].headers["X-CSRF-Token"] == "fresh-csrf-token"
    from urllib.parse import parse_qs

    form = parse_qs(seen[1].content.decode("utf-8"))
    assert form["_token"] == ["fresh-csrf-token"]


@pytest.mark.asyncio
async def test_custom_write_redirect_has_unknown_outcome_and_is_not_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET" and request.url.path == "/Switchfy/client/numbers":
            return _website_page_response()
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
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_custom_write_csrf_rejection_is_not_bypassed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/Switchfy/client/numbers":
            return _website_page_response()
        return httpx.Response(419, json={"message": "CSRF token mismatch"})

    settings = _custom_write_settings()
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=SecretStr("test-only-key"),
        transport=httpx.MockTransport(handler),
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
        return _website_page_response()

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
                "termination_id": "12345",
                "termination_term_id": "123456",
                "count": 0,
                "sort_type": "random",
            }
        )
    assert called is False


@pytest.mark.asyncio
async def test_add_number_rejects_count_above_live_metadata_without_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET" and request.url.path == "/Switchfy/client/numbers":
            return _website_page_response()
        if request.method == "GET" and request.url.path == "/Switchfy/client/numbers/terminations":
            return _termination_metadata_response()
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"success": True})

    settings = _custom_write_settings()
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=SecretStr("test-only-key"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AugestelIntegrationError, match="max_per_request"):
        await client.add_numbers(
            {
                "termination_id": "12345",
                "termination_term_id": "123456",
                "count": 11,
                "sort_type": "random",
            }
        )
    assert [request.method for request in seen] == ["GET", "GET"]



@pytest.mark.asyncio
async def test_list_terminations_returns_safe_choices_without_request_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET" and request.url.path == "/Switchfy/client/numbers":
            return _website_page_response()
        if request.method == "GET" and request.url.path == "/Switchfy/client/numbers/terminations":
            return _termination_metadata_response()
        return httpx.Response(404, json={"success": False})

    settings = _custom_write_settings()
    monkeypatch.setattr(augestel, "get_settings", lambda: settings)
    client = AugestelClient(
        base_url=settings.augestel_api_base_url,
        api_key=SecretStr("test-only-key"),
        transport=httpx.MockTransport(handler),
    )

    result = await client.list_terminations()

    assert result["success"] is True
    assert [request.method for request in seen] == ["GET", "GET"]
    term = result["terminations"][0]
    assert term["id"] == "12345"
    assert term["terms"][0]["id"] == "123456"
    assert term["number_sort_type"] == "random"
    assert "request_token" not in term
    assert "request_token" not in term["terms"][0]
    assert seen[1].headers["X-CSRF-Token"] == "fresh-csrf-token"
