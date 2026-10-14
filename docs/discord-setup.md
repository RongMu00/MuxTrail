# Discord Gateway setup

1. Create an application in the Discord Developer Portal and add a bot.
2. Copy the bot token to `DISCORD_BOT_TOKEN`.
3. No privileged intent is required. MuxTrail requests Guilds, Guild Messages, and Direct Messages.
4. In OAuth2 URL Generator, select `bot`, then grant View Channels, Send Messages, Read Message
   History, and Send Messages in Threads.
5. Install the generated URL into a test server.
6. Set `MUXTRAIL_DISCORD_ENABLED=true` and restart MuxTrail.

DMs are processed directly. Server messages must mention `@MuxTrail`. Gateway events are
deduplicated and self/bot messages are ignored. Replies use REST, preserve a message reference on
the first chunk, and split text at Discord's 2,000-character limit. Heartbeats, reconnect, and
session resume are handled by the adapter. Session identity includes server, channel/thread, and
user.

A live round trip requires valid credentials; mocked Gateway/REST tests run without them.
