# Troubleshooting

- **No model response:** confirm one provider key is set. Missing, invalid, billing, rate-limit,
  unsupported-model, timeout, and server failures are reported as distinct safe errors.
- **Slack does not connect:** verify both token types, Socket Mode, scopes, subscriptions, and app
  installation. `xapp-` and `xoxb-` tokens are different.
- **Discord sees no server text:** mention the bot member or its Discord-managed bot role first;
  both encodings are supported, while unrelated role mentions are ignored. MuxTrail avoids the privileged Message
  Content intent by default because Discord documents content access for DMs and explicit app
  mentions. If server events still arrive with empty `content` and `mentions`, follow the opt-in
  workaround in [Discord Gateway setup](discord-setup.md): enable Message Content Intent in the
  Developer Portal, set `MUXTRAIL_DISCORD_MESSAGE_CONTENT_ENABLED=true`, and restart MuxTrail.
- **Search returns zero results:** inspect filters and retry with broader terms. Zero results are not
  proof that information is absent.
- **Fetch blocked:** the destination may resolve to a private address, redirect unsafely, return a
  binary type, exceed 2 MB, or reject automated clients.
- **WebSocket disconnected:** the workbench reconnects with bounded exponential backoff. Verify the
  Gateway is listening on port 18789 and the Vite proxy configuration is intact.
