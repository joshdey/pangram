import logging
from collections.abc import Callable
from decimal import Decimal
from typing import Self, TypeVar

from slack_sdk.errors import SlackApiError, SlackRequestError

from pangram_slack.config import Config
from pangram_slack.integrations.pangram.client import PangramClient
from pangram_slack.integrations.slack.client import SlackClient
from pangram_slack.presenter import format_analysis
from pangram_slack.types.pangram import PangramAnalysisRequest
from pangram_slack.types.slack import (
    SlackAppMention,
    SlackMessage,
    find_slack_message_reference,
)

Result = TypeVar("Result")
logger = logging.getLogger(__name__)


class CrossChannelTargetError(ValueError):
    """A linked message is outside the invoking channel."""


class PangramAnalysisService:
    """Resolve a requested Slack message, analyze it, and post the result."""

    def __init__(
        self,
        *,
        config: Config,
        pangram_client: PangramClient,
        slack_client: SlackClient,
    ) -> None:
        self._config = config
        self._pangram_client = pangram_client
        self._slack_client = slack_client

    def analyze_mention(self, mention: SlackAppMention) -> None:
        """Analyze the message targeted by an authorized Slack mention."""
        if not self._config.is_user_allowed(mention.user):
            return
        try:
            target = self._resolve_target_message(mention)
        except CrossChannelTargetError:
            self._reply(mention, "The target message must be in the same channel.")
            return
        except (SlackApiError, SlackRequestError, OSError):
            self._reply(
                mention,
                "I couldn't read that message. Check that I'm invited to the channel "
                "and have permission to read its history.",
            )
            return
        if target is None:
            self._reply(
                mention,
                "Tag me after a text message in a thread, or include a message's "
                "Slack link from this channel.",
            )
            return

        self._optional_slack_call(
            lambda: self._slack_client.add_reaction(
                channel=mention.channel, name="eyes", timestamp=target.ts
            )
        )
        source_permalink = self._optional_slack_call(
            lambda: self._slack_client.get_message_permalink(
                channel=mention.channel, timestamp=target.ts
            )
        )
        self._optional_slack_call(
            lambda: self._slack_client.set_status(
                channel=mention.channel,
                loading_messages=["Running the Pangram analysis…"],
                status="is analyzing the selected message…",
                thread_ts=mention.reply_ts,
            )
        )
        try:
            try:
                analysis = self._pangram_client.analyze(
                    PangramAnalysisRequest(
                        include_dashboard_link=self._config.pangram_include_dashboard_link,
                        model=self._config.pangram_model,
                        text=target.text,
                    )
                )
            except Exception:
                self._reply(
                    mention,
                    ":warning: I couldn't analyze that message. Check the Pangram "
                    "service, API key, and configured model.",
                )
                raise
            self._slack_client.post_message(
                channel=mention.channel,
                text=format_analysis(analysis, source_permalink),
                thread_ts=mention.reply_ts,
            )
            reaction_names = (
                ["shame-nun", "hadtodoittoem"] if analysis.contains_ai else ["100"]
            )
            for reaction_name in reaction_names:
                self._optional_slack_call(
                    lambda reaction_name=reaction_name: self._slack_client.add_reaction(
                        channel=mention.channel, name=reaction_name, timestamp=target.ts
                    )
                )
        finally:
            self._optional_slack_call(
                lambda: self._slack_client.set_status(
                    channel=mention.channel,
                    loading_messages=[],
                    status="",
                    thread_ts=mention.reply_ts,
                )
            )
            self._optional_slack_call(
                lambda: self._slack_client.remove_reaction(
                    channel=mention.channel, name="eyes", timestamp=target.ts
                )
            )

    @classmethod
    def default(cls, *, config: Config, slack_client: SlackClient) -> Self:
        """Wire the service to the default Pangram client."""
        return cls(
            config=config,
            pangram_client=PangramClient.default(
                config.pangram_api_key.get_secret_value()
            ),
            slack_client=slack_client,
        )

    def _is_eligible(self, message: SlackMessage) -> bool:
        return (
            message.user != self._slack_client.bot_user_id
            and not message.bot_id
            and message.subtype not in {"message_changed", "message_deleted"}
            and bool(message.text.strip())
        )

    def _optional_slack_call(self, operation: Callable[[], Result]) -> Result | None:
        try:
            return operation()
        except (SlackApiError, SlackRequestError, OSError) as error:
            logger.warning("Optional Slack operation failed (%s)", type(error).__name__)
            return None

    def _reply(self, mention: SlackAppMention, text: str) -> None:
        self._optional_slack_call(
            lambda: self._slack_client.post_message(
                channel=mention.channel, text=text, thread_ts=mention.reply_ts
            )
        )

    def _resolve_target_message(self, mention: SlackAppMention) -> SlackMessage | None:
        explicit_target = find_slack_message_reference(mention.text)
        if explicit_target is not None:
            if explicit_target.channel != mention.channel:
                raise CrossChannelTargetError(
                    "The target message must be in the same channel"
                )
            messages = self._slack_client.list_thread_messages(
                channel=mention.channel,
                thread_ts=explicit_target.ts,
            )
            for message in messages:
                if message.ts == explicit_target.ts and self._is_eligible(message):
                    return message
            return None

        if mention.thread_ts is None:
            return None

        messages = self._slack_client.list_thread_messages(
            channel=mention.channel,
            thread_ts=mention.thread_ts,
        )
        candidates = [
            message
            for message in messages
            if Decimal(message.ts) < Decimal(mention.ts) and self._is_eligible(message)
        ]
        return max(candidates, key=lambda message: Decimal(message.ts), default=None)
