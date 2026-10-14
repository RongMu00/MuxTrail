# Architecture

MuxTrail has one execution path for every channel:

```text
WebChat / Slack / Discord / Feishu
  → channel adapter
  → normalized InboundMessage
  → GatewayRuntime._handle_inbound
  → stable session key + transcript history
  → EmbeddedRuntime
  → model provider ↔ allowlisted tools
  → normalized OutboundMessage
  → originating channel adapter
```

`InboundMessage` carries channel, account/workspace, user, conversation, thread, message,
attachments, capabilities, reply target, and trace identity. Session keys include each namespace
dimension to prevent cross-channel, cross-workspace, cross-thread, and cross-user collisions.

Every inbound event receives a trace ID. The workbench receives the same runtime event format for
channel receipt, session loading, context assembly, provider output, tool calls/results, usage,
final response, errors, latency, and channel delivery. Sensitive values are redacted before they
reach logs or browser state.
