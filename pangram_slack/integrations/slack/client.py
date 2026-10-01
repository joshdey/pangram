from typing import Self

from slack_sdk import WebClient

from pangram_slack.types.slack import SlackMessage


class SlackClient:
    """Client boundary for the Slack Web API calls used by the app."""

    def __init__(self, *, bot_user_id: str, client: WebClient) -> None:
        self._bot_user_id = bot_user_id
        self._client = client

    @classmethod
    def default(cls, client: WebClient) -> Self:
        """Create a Slack client and resolve the installed bot's user ID."""
        bot_user_id = str(client.auth_test()["user_id"])
        return cls(bot_user_id=bot_user_id, client=client)

    @property
    def bot_user_id(self) -> str:
        """Return the installed bot's Slack user ID."""
        return self._bot_user_id

    def get_message_permalink(self, *, channel: str, timestamp: str) -> str | None:
        """Return a permalink for a Slack message."""
        response = self._client.chat_getPermalink(
            channel=channel,
            message_ts=timestamp,
        )
        permalink = response.get("permalink")
        return str(permalink) if permalink else None

    def add_reaction(self, *, channel: str, name: str, timestamp: str) -> None:
        """Add a reaction to a Slack message."""
        self._client.reactions_add(
            channel=channel,
            name=name,
            timestamp=timestamp,
        )

    def list_thread_messages(self, *, channel: str, thread_ts: str) -> list[SlackMessage]:
        """Return messages from one Slack thread."""
        messages: list[SlackMessage] = []
        cursor = ""
        while True:
            response = self._client.conversations_replies(
                channel=channel,
                cursor=cursor,
                limit=200,
                ts=thread_ts,
            )
            messages.extend(
                SlackMessage.model_validate(message)
                for message in response.get("messages", [])
            )
            cursor = response.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                return messages

    def post_message(self, *, channel: str, text: str, thread_ts: str) -> None:
        """Post a reply into a Slack thread."""
        self._client.chat_postMessage(
            channel=channel,
            text=text,
            thread_ts=thread_ts,
            unfurl_links=False,
        )

    def remove_reaction(self, *, channel: str, name: str, timestamp: str) -> None:
        """Remove a reaction from a Slack message."""
        self._client.reactions_remove(
            channel=channel,
            name=name,
            timestamp=timestamp,
        )

    def set_status(
        self,
        *,
        channel: str,
        loading_messages: list[str],
        status: str,
        thread_ts: str,
    ) -> None:
        """Set Slack's native loading status for a thread."""
        self._client.assistant_threads_setStatus(
            channel_id=channel,
            loading_messages=loading_messages,
            status=status,
            thread_ts=thread_ts,
        )
