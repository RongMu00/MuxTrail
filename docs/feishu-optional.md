# Optional Feishu integration

Feishu is disabled by default and isolated from the English-first core experience. To enable it,
set `MUXTRAIL_FEISHU_ENABLED=true`, `FEISHU_APP_ID`, and `FEISHU_APP_SECRET`. The existing
long-connection adapter preserves text ingress, mention filtering, bot filtering, deduplication,
thread-style replies, and optional document tools.

Document writes also require `MUXTRAIL_FEISHU_DOCS_WRITE_ENABLED=true` and explicit user intent.
The signed internal sidecar endpoint uses `MUXTRAIL_FEISHU_INTERNAL_SECRET`.

Migration: the current names use the `MUXTRAIL_` prefix. No legacy product-prefixed environment
variables are read. Existing Feishu platform credential names remain unchanged because Feishu owns
those names.
