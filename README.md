# Pangram Slack Checker

got tired of reading blocks of ai slop on slack. time to shame.
<img width="878" height="344" alt="CleanShot 2026-10-01 at 10 54 51@2x" src="https://github.com/user-attachments/assets/44335a7a-da2d-4882-b097-2f499841c437" />
<img width="868" height="350" alt="CleanShot 2026-10-01 at 10 56 17@2x" src="https://github.com/user-attachments/assets/777d940b-ffcd-4d54-a85f-4fbd8c8f48ea" />
<img width="862" height="352" alt="CleanShot 2026-10-01 at 10 56 58@2x" src="https://github.com/user-attachments/assets/05b9cf57-bc94-496b-a4ac-0244ed950ad6" />

below written by codex

## Requirements

- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).
- A Slack workspace where you can create and install an app.
- A Pangram API key with access to the configured model.
- The bot must be invited to the channels where you want to use it.

## Set up the Slack app

1. Open [Slack's app management page](https://api.slack.com/apps) and choose
   **Create New App** → **From an app manifest**.
2. Select your workspace and paste the contents of `manifest.yaml`.
3. Under **Basic Information** → **App-Level Tokens**, generate a token with the
   `connections:write` scope. Use this `xapp-...` token as `SLACK_APP_TOKEN`.
4. Under **OAuth & Permissions**, install the app and copy its `xoxb-...` bot token
   into `SLACK_BOT_TOKEN`.
5. Invite the app to a test channel. Reinstall it after changing scopes.

The manifest names the bot **Pangram** and requests `app_mentions:read`,
`channels:history`, `groups:history`, `chat:write`, and `reactions:write` for receiving
mentions, reading channel threads, posting replies, and managing reactions.

## Configure and run

```bash
cp .env.example .env
# Edit .env with your credentials and allowed Slack member IDs.
uv sync --locked --extra dev
uv run pangram-slack-bot
```

Configuration is loaded from the environment and a local `.env` file. Existing
environment values take precedence over `.env` values.

- `SLACK_APP_TOKEN`: required Socket Mode app-level token.
- `SLACK_BOT_TOKEN`: required bot token for the installed Slack app.
- `SLACK_ALLOWED_USER_IDS`: required comma-separated list of Slack member IDs, such
  as `U0123456789,U9876543210`. In Slack, open your profile's three-dot menu and
  choose **Copy member ID**.
- `PANGRAM_API_KEY`: required Pangram API key.
- `PANGRAM_MODEL`: model to request; defaults to `default`. Use a model available
  to your API key.
- `PANGRAM_PUBLIC_DASHBOARD_LINK`: defaults to `false`. `true`, `yes`, or `1` enables
  a public Pangram report link. Enable it only when viewers of that link may access
  the analyzed text.
- Blank credentials, empty allowlists, blank model names, and invalid boolean values
  are rejected at startup.
- `LOG_LEVEL`: Python logging level; defaults to `INFO`.

Socket Mode needs no public webhook URL. The bot works only while the process is
running and connected to Slack. This app is intended for a single workspace.

## Behavior

### Triggering an analysis

Use Slack's mention picker to tag `@Pangram`. If you renamed the bot, mention that
name instead. The word `check` is a convention: the current handler processes every
mention from an allowed user, regardless of command wording.

Only IDs in `SLACK_ALLOWED_USER_IDS` may invoke the bot. Other users' mentions receive
a `:no_good:` reaction and do not trigger a Pangram request.

### Selecting the message

- **Without a link:** start or open a thread, then post `@Pangram check` after the
  message you want analyzed. The bot selects the latest earlier message in that
  thread that has nonblank text, is not from a bot, and is not a changed/deleted
  message event. This can be the thread's original message or an earlier reply.
- **With a link:** post `@Pangram check <Slack message link>` in the same channel.
  The bot uses the first recognized Slack message link and looks for that exact
  message timestamp. Bot messages are excluded.
- **No target:** a mention outside a thread without a link, or a lookup with no
  eligible target, receives instructions for selecting a message.
- **Cross-channel links:** rejected even if you can access both channels. A message
  link does not grant the bot channel access. The bot replies with an explanation.

Only the selected message's `text` is sent to Pangram. Files, attachments, and the
whole thread are not analyzed together. Both selection paths exclude bot messages, blank text, and changed/deleted
message events.

### Loading, results, and reactions

The bot adds `:eyes:` to the selected message and requests Slack's native thread
loading status. It sends the text using `PANGRAM_MODEL`, then posts the prediction,
AI-written, AI-assisted, and human percentages, plus a link to the source message.
An optional public Pangram report link is included when enabled and returned by the API.

Results appear in the **invoking thread**, which may differ from the target message's
thread when using a link. A top-level mention with a link gets a reply beneath that
mention. Other channel members can see the reply; the allowlist restricts invocation,
not result visibility.

After posting the result, the bot removes `:eyes:` and adds:

- `:100:` when both reported AI fractions are zero.
- Both `:shame-nun:` and `:hadtodoittoem:` when either AI fraction is greater than zero.

The two AI-result reactions are custom emoji and must exist in your workspace.
Reaction names and thresholds are currently hardcoded. Percentages are rounded to
whole numbers, so a small nonzero fraction may display as `0%` while still triggering
AI reactions. The reactions reflect the detector output; they do not establish authorship.

### Failure behavior

If the Pangram request or response validation fails, the bot attempts to clear the
loading status, remove `:eyes:`, and post a warning. Reactions, loading status, and source links are best-effort: failures do not
prevent analysis or result delivery. Cleanup is attempted after analysis and delivery,
including on failure; Slack outages can still prevent cleanup. Message-read failures
receive a permission/access hint. Result-delivery failures are logged. Results already posted are not rolled back if a later
reaction fails.

## Verification

```bash
uv run ruff check .
uv run python -m unittest discover -s tests -v
```

For a manual smoke check:

1. Invite the bot to a test channel and create a message containing text.
2. Start a thread and post `@Pangram check` from an allowed account.
3. Confirm the response links to the intended message and includes the percentages.
4. Try an explicit message link from the same channel.
5. Try a mention from an account outside the allowlist and confirm it is not analyzed.

## Operational limitations and troubleshooting

- Thread history is read across all pages; long threads require more Slack API calls.
- Missing custom emoji are logged and skipped without interrupting analysis.
- If no response appears, check bot membership, the user allowlist, Slack scopes,
  and process logs. For Pangram failures, also check the API key and configured model.
- Event deduplication is in memory, resets on restart, and evicts the oldest event when its cache
  reaches capacity. It does not guarantee exactly-once analysis or billing. Run one
  process; multiple replicas would need shared, durable deduplication.
- Separate mentions can analyze the same message again. There is no per-user cooldown
  or message-result cache, and concurrent analyses can interfere with shared reactions.

## Privacy and local files

The selected message text is sent to Pangram, an external processor. Confirm that
your workspace permits this. Detector results are probabilistic signals and do not
establish authorship. Public report links are disabled by default.

Application info logs include Slack user IDs, channel IDs, and authorization status.
They do not intentionally include message text or credentials. Application failure logs record exception types without exception payloads.
SDK debug logging may contain additional data; review logs before sharing them.

Keep credentials in `.env` or your deployment environment. `.gitignore` excludes
local environment files (except `.env.example`), private key files, personal
`unauthorized-users.md` notes, and the `outputs/` and `work/` directories, along with
Python environments and generated artifacts. Review staged files before publishing;
ignore rules do not remove secrets already committed to Git history.

## Code structure

- `pangram_slack/app.py`: Slack Bolt setup, authorization, event deduplication, and
  the top-level error boundary.
- `pangram_slack/config.py`: environment configuration.
- `pangram_slack/service.py`: message selection and analysis workflow.
- `pangram_slack/integrations/`: Slack and Pangram SDK clients.
- `pangram_slack/types/`: Pydantic contracts for external data.
- `pangram_slack/presenter.py`: Slack result formatting.
