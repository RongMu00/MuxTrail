# Discord Gateway setup

1. Create an application in the Discord Developer Portal and add a bot.
2. Copy the bot token to `DISCORD_BOT_TOKEN`.
3. Leave privileged intents disabled initially. MuxTrail's default Guilds, Guild Messages, and
   Direct Messages intents support DMs and explicit app mentions under Discord's documented
   message-content exceptions.
4. In OAuth2 URL Generator, select `bot`, then grant View Channels, Send Messages, Read Message
   History, and Send Messages in Threads.
5. Install the generated URL into a test server.
6. Set `MUXTRAIL_DISCORD_ENABLED=true` and restart MuxTrail.

DMs are processed directly. Server messages must mention `@MuxTrail`. Gateway events are
deduplicated and self/bot messages are ignored. Replies use REST, preserve a message reference on
the first chunk, and split text at Discord's 2,000-character limit. Heartbeats, reconnect, and
session resume are handled by the adapter. Session identity includes server, channel/thread, and
user.

If your Discord environment delivers server events with both `content` and `mentions` empty,
enable **Message Content Intent** under **Privileged Gateway Intents** in the Developer Portal,
set `MUXTRAIL_DISCORD_MESSAGE_CONTENT_ENABLED=true`, and restart MuxTrail. This is an opt-in
compatibility workaround, not a default requirement. Both switches must agree: requesting the
intent in MuxTrail without enabling it for the bot in the Developer Portal can make Discord close
the Gateway connection with code `4014` (disallowed intent).

A live round trip requires valid credentials; mocked Gateway/REST tests run without them.
