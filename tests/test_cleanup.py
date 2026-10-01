import unittest
from unittest.mock import create_autospec, patch

from pydantic import ValidationError
from slack_sdk import WebClient
from slack_sdk.errors import SlackRequestError

from pangram_slack.app import EventDeduplicator
from pangram_slack.config import Config
from pangram_slack.integrations.pangram.client import PangramClient
from pangram_slack.integrations.slack.client import SlackClient
from pangram_slack.service import PangramAnalysisService
from pangram_slack.types.pangram import PangramAnalysisResponse
from pangram_slack.types.slack import SlackAppMention, SlackMessage


class CleanupTests(unittest.TestCase):
    def test_analysis_cleanup_on_failure(self):
        for failure in ("analysis", "delivery", "decoration", "cleanup"):
            with self.subTest(failure=failure):
                # ARRANGE
                config = Config(
                    allowed_user_ids={"U123"},
                    pangram_api_key="secret-pangram",
                    pangram_include_dashboard_link=False,
                    pangram_model="default",
                    slack_app_token="secret-app",
                    slack_bot_token="secret-bot",
                )
                slack = create_autospec(SlackClient, instance=True)
                pangram = create_autospec(PangramClient, instance=True)
                slack.list_thread_messages.return_value = [
                    SlackMessage(text="selected", ts="1.000001", user="U456")
                ]
                slack.get_message_permalink.return_value = None
                pangram.analyze.return_value = PangramAnalysisResponse(
                    fraction_ai=0,
                    fraction_ai_assisted=0,
                    fraction_human=1,
                    prediction="Human",
                    prediction_short="Human",
                )
                if failure == "analysis":
                    pangram.analyze.side_effect = RuntimeError("upstream failure")
                if failure == "delivery":
                    slack.post_message.side_effect = SlackRequestError("delivery")
                if failure == "decoration":
                    slack.add_reaction.side_effect = SlackRequestError("emoji")
                    slack.set_status.side_effect = SlackRequestError("status")
                    slack.get_message_permalink.side_effect = SlackRequestError("link")
                if failure == "cleanup":
                    slack.set_status.side_effect = [None, SlackRequestError("status")]
                service = PangramAnalysisService(
                    config=config,
                    pangram_client=pangram,
                    slack_client=slack,
                )
                mention = SlackAppMention(
                    channel="C123",
                    text="check",
                    thread_ts="1.000001",
                    ts="2.000001",
                    user="U123",
                )

                # ACT
                if failure in {"analysis", "delivery"}:
                    with self.assertRaises((RuntimeError, SlackRequestError)):
                        service.analyze_mention(mention)
                else:
                    service.analyze_mention(mention)

                # ASSERT
                pangram.analyze.assert_called_once()
                slack.remove_reaction.assert_called_once_with(
                    channel="C123",
                    name="eyes",
                    timestamp="1.000001",
                )
                self.assertEqual(slack.set_status.call_args.kwargs["status"], "")
                if failure == "analysis":
                    self.assertIn(
                        "couldn't analyze", slack.post_message.call_args.kwargs["text"]
                    )

    def test_configuration_rejects_invalid_values_and_masks_secrets(self):
        # ARRANGE
        values = {
            "allowed_user_ids": {"U123"},
            "pangram_api_key": "secret-pangram",
            "pangram_include_dashboard_link": False,
            "pangram_model": "default",
            "slack_app_token": "secret-app",
            "slack_bot_token": "secret-bot",
        }
        for name, value in (
            ("allowed_user_ids", set()),
            ("pangram_model", " "),
            ("pangram_api_key", " "),
            ("slack_app_token", " "),
            ("slack_bot_token", " "),
        ):
            # ACT / ASSERT
            with self.subTest(name=name), self.assertRaises(ValidationError):
                Config(**(values | {name: value}))
        # ACT
        config = Config(**values)
        # ASSERT
        self.assertNotIn("secret-", repr(config))

    def test_deduplication_retains_recent_events_at_capacity(self):
        # ARRANGE
        deduplicator = EventDeduplicator()
        # ACT
        for index in range(10_001):
            deduplicator.claim(str(index))
        # ASSERT
        self.assertFalse(deduplicator.claim("10000"))
        self.assertFalse(deduplicator.claim("5000"))
        self.assertTrue(deduplicator.claim("0"))

    def test_thread_pagination(self):
        # ARRANGE
        client = create_autospec(WebClient, instance=True)
        client.conversations_replies.side_effect = [
            {
                "messages": [{"text": "first", "ts": "1.000001"}],
                "response_metadata": {"next_cursor": "page-two"},
            },
            {"messages": [{"text": "last", "ts": "2.000001"}]},
        ]
        slack = SlackClient(bot_user_id="BOT", client=client)
        # ACT
        messages = slack.list_thread_messages(channel="C123", thread_ts="1.000001")
        # ASSERT
        self.assertEqual([message.text for message in messages], ["first", "last"])
        self.assertEqual(
            client.conversations_replies.call_args.kwargs["cursor"], "page-two"
        )

    def test_invalid_environment_boolean(self):
        # ARRANGE
        environment = {
            "SLACK_ALLOWED_USER_IDS": "U123",
            "PANGRAM_API_KEY": "test",
            "SLACK_APP_TOKEN": "test",
            "SLACK_BOT_TOKEN": "test",
            "PANGRAM_PUBLIC_DASHBOARD_LINK": "typo",
        }
        # ACT / ASSERT
        with (
            patch.dict("os.environ", environment, clear=True),
            self.assertRaisesRegex(RuntimeError, "Invalid boolean"),
        ):
            Config.default()

    def test_targeting_and_authorization(self):
        for case in (
            "unauthorized",
            "cross-channel",
            "blank-link",
            "deleted-link",
            "latest",
        ):
            with self.subTest(case=case):
                # ARRANGE
                config = Config(
                    allowed_user_ids={"U123"},
                    pangram_api_key="test",
                    pangram_include_dashboard_link=False,
                    pangram_model="default",
                    slack_app_token="test",
                    slack_bot_token="test",
                )
                slack = create_autospec(SlackClient, instance=True)
                pangram = create_autospec(PangramClient, instance=True)
                slack.get_message_permalink.return_value = None
                pangram.analyze.return_value = PangramAnalysisResponse(
                    fraction_ai=0,
                    fraction_ai_assisted=0,
                    fraction_human=1,
                    prediction="Human",
                    prediction_short="Human",
                )
                target = SlackMessage(
                    text=" " if case == "blank-link" else "target",
                    ts="1.000001",
                    user="U456",
                    subtype="message_deleted" if case == "deleted-link" else None,
                )
                slack.list_thread_messages.return_value = [target]
                text = "check https://example.slack.com/archives/C123/p00001000001"
                if case == "cross-channel":
                    text = text.replace("C123", "C999")
                if case == "latest":
                    text = "check"
                    slack.list_thread_messages.return_value = [
                        target,
                        SlackMessage(text="latest", ts="2.000001", user="U456"),
                        SlackMessage(text="bot", ts="2.000002", bot_id="B123"),
                        SlackMessage(text="future", ts="4.000001", user="U456"),
                    ]
                mention = SlackAppMention(
                    channel="C123",
                    text=text,
                    thread_ts="1.000001",
                    ts="3.000001",
                    user="OTHER" if case == "unauthorized" else "U123",
                )
                service = PangramAnalysisService(
                    config=config,
                    pangram_client=pangram,
                    slack_client=slack,
                )
                # ACT
                service.analyze_mention(mention)
                # ASSERT
                if case == "latest":
                    self.assertEqual(pangram.analyze.call_args.args[0].text, "latest")
                else:
                    pangram.analyze.assert_not_called()
                if case in {"unauthorized", "cross-channel"}:
                    slack.list_thread_messages.assert_not_called()
