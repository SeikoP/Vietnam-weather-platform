from src.config.settings import Settings


def test_settings_disable_discord_notifications_by_default() -> None:
    settings = Settings(database_url="postgresql+psycopg://user:pass@localhost:5432/vwdp")

    assert settings.discord_notifications_enabled is False
    assert settings.discord_webhook_url is None


def test_settings_require_webhook_when_discord_notifications_enabled() -> None:
    try:
        Settings(
            database_url="postgresql+psycopg://user:pass@localhost:5432/vwdp",
            discord_notifications_enabled=True,
        )
    except ValueError as exc:
        assert "DISCORD_WEBHOOK_URL" in str(exc)
    else:
        raise AssertionError(
            "Expected Settings to reject enabled Discord notifications without webhook"
        )
