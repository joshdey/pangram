import logging
import os
from collections import OrderedDict
from collections.abc import Mapping
from threading import Lock
from typing import Any

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError, SlackRequestError

from pangram_slack.config import Config
from pangram_slack.integrations.slack.client import SlackClient
from pangram_slack.service import PangramAnalysisService
from pangram_slack.types.slack import SlackAppMention


class EventDeduplicator:
    """Prevent Slack retries from creating duplicate Pangram charges."""

    _MAX_EVENT_IDS = 10_000

    def __init__(self) -> None:
        self._event_ids: OrderedDict[str, None] = OrderedDict()
        self._lock = Lock()

    def claim(self, event_id: str) -> bool:
        """Return whether this process has not handled the event before."""
        with self._lock:
            if event_id in self._event_ids:
                return False
            if len(self._event_ids) >= self._MAX_EVENT_IDS:
                self._event_ids.popitem(last=False)
            self._event_ids[event_id] = None
            return True


def create_app(config: Config | None = None) -> App:
    """Create and wire the Slack application."""
    config = config or Config.default()
    app = App(token=config.slack_bot_token.get_secret_value())
    deduplicator = EventDeduplicator()
    slack_client = SlackClient.default(app.client)
    service = PangramAnalysisService.default(
        config=config,
        slack_client=slack_client,
    )

    @app.event("app_mention")
    def handle_app_mention(
        body: Mapping[str, Any],
        event: Mapping[str, Any],
        logger: logging.Logger,
    ) -> None:
        mention = SlackAppMention.model_validate(event)
        event_id = str(body.get("event_id", mention.ts))
        if not deduplicator.claim(event_id):
            return

        is_authorized = config.is_user_allowed(mention.user)
        logger.info(
            "Received Pangram mention user_id=%s channel_id=%s authorized=%s",
            mention.user,
            mention.channel,
            is_authorized,
        )
        if not is_authorized:
            try:
                slack_client.add_reaction(
                    channel=mention.channel,
                    name="no_good",
                    timestamp=mention.ts,
                )
            except (SlackApiError, SlackRequestError, OSError):
                logger.warning("Failed to react to unauthorized Slack event %s", event_id)
            return

        try:
            service.analyze_mention(mention)
        except Exception as error:  # noqa: BLE001
            logger.error(
                "Pangram analysis failed for Slack event %s (%s)",
                event_id,
                type(error).__name__,
            )

    return app


def main() -> None:
    """Run the app locally over Slack Socket Mode."""
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    config = Config.default()
    SocketModeHandler(
        create_app(config), config.slack_app_token.get_secret_value()
    ).start()


if __name__ == "__main__":
    main()
