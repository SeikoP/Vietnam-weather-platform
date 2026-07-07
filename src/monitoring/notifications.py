from dataclasses import dataclass

import requests

from src.config.settings import Settings


@dataclass(frozen=True)
class NotificationResult:
    sent: bool
    reason: str


class DiscordNotifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def notify_failure(self, title: str, details: str) -> NotificationResult:
        if not self._settings.discord_notifications_enabled:
            return NotificationResult(sent=False, reason="discord notifications disabled")
        if not self._settings.discord_webhook_url:
            return NotificationResult(sent=False, reason="discord webhook missing")

        response = requests.post(
            self._settings.discord_webhook_url,
            json={"content": f"**{title}**\n{details}"},
            timeout=10,
        )
        response.raise_for_status()
        return NotificationResult(sent=True, reason="sent")
