import re

from pydantic import BaseModel, ConfigDict


class SlackAppMention(BaseModel):
    """Slack app_mention fields used by the application."""

    model_config = ConfigDict(extra="ignore")

    channel: str
    text: str
    thread_ts: str | None = None
    ts: str
    user: str

    @property
    def reply_ts(self) -> str:
        """Return the thread in which the app should reply."""
        return self.thread_ts or self.ts


class SlackMessage(BaseModel):
    """Slack message fields used for target selection."""

    model_config = ConfigDict(extra="ignore")

    bot_id: str | None = None
    subtype: str | None = None
    text: str = ""
    ts: str
    user: str | None = None


class SlackMessageReference(BaseModel):
    """Channel and message timestamp parsed from a Slack permalink."""

    channel: str
    ts: str


_SLACK_PERMALINK_PATTERN = re.compile(
    r"https://[^\s<>]+\.slack\.com/archives/"
    r"(?P<channel>[A-Z0-9]+)/p(?P<stamp>\d{11,})"
)


def find_slack_message_reference(text: str) -> SlackMessageReference | None:
    """Parse the first Slack message permalink in text."""
    match = _SLACK_PERMALINK_PATTERN.search(text)
    if match is None:
        return None

    stamp = match.group("stamp")
    timestamp = f"{stamp[:-6]}.{stamp[-6:]}"
    return SlackMessageReference(
        channel=match.group("channel"),
        ts=timestamp,
    )
