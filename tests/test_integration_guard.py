import pytest

from app.integrations.augestel import AugestelClient, AugestelIntegrationDisabled


@pytest.mark.asyncio
async def test_export_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUGESTEL_INTEGRATION_ENABLED", "false")
    client = AugestelClient(base_url="https://augestel.com")
    with pytest.raises(AugestelIntegrationDisabled):
        await client.get_export()
