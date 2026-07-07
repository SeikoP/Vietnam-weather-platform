from src.config.settings import Settings
from src.monitoring.notifications import DiscordNotifier


def test_discord_notifier_does_not_send_when_disabled() -> None:
    settings = Settings(database_url="postgresql+psycopg://user:pass@localhost:5432/vwdp")

    result = DiscordNotifier(settings).notify_failure("failure", "details")

    assert result.sent is False
    assert result.reason == "discord notifications disabled"
