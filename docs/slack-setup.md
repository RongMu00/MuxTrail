# Slack Socket Mode setup

1. Create a Slack app at `api.slack.com/apps` and choose the target workspace.
2. Enable Socket Mode and create an app-level token with `connections:write`.
3. Under OAuth scopes, add `app_mentions:read`, `chat:write`, `im:history`, and
   `channels:history` (add private-channel history only if you intentionally need it).
4. Subscribe the bot to `app_mention` and `message.im` events.
5. Install or reinstall the app to the workspace.
6. Set `MUXTRAIL_SLACK_ENABLED=true`, `SLACK_APP_TOKEN=xapp-…`, and
   `SLACK_BOT_TOKEN=xoxb-…`; restart MuxTrail.

DMs are processed directly. Channel messages must mention `@MuxTrail`. The Socket Mode envelope is
acknowledged before processing, retry/event IDs are deduplicated, bot messages are ignored, and
responses are posted into the originating DM or thread. Session identity includes workspace,
channel/thread, and user.

Test by sending a DM, then mentioning the bot in a channel and continuing in its thread. A live
round trip requires valid credentials; the repository test suite uses mocked events and API calls.
