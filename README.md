# MuxTrail

> An observable, local-first AI gateway for running one tool-using assistant across WebChat,
> Slack, Discord, and optional Feishu channels.

MuxTrail is an English-first developer tool for inspecting the complete path of an agent turn:

`channel event → gateway → session → model → tool calls → model result → channel reply`

It is designed for AI infrastructure, backend, developer-tools, and applied AI engineers—and
for teams evaluating agent reliability.

## Architecture

Every channel normalizes incoming events into the same contract and calls the same Gateway.
The Gateway assigns a trace ID and collision-resistant session key, loads the transcript, and
invokes the shared embedded runtime. Model tool calls pass through one allowlisted tool registry;
results return to model context before a normal final answer is delivered through the originating
adapter. See [Architecture](docs/architecture.md).

## Feature status

| Capability | Status | Notes |
|---|---|---|
| WebChat workbench | Implemented | Default local channel; streaming trace, tools, reset, reconnect |
| Slack Socket Mode | Implemented | DMs, mentions, threads, deduplication, retries, reconnect |
| Discord Gateway + REST | Implemented | DMs, mentions, message references, heartbeat/resume, splitting |
| Feishu long connection | Optional | Disabled by default; isolated guide and credentials |
| Tavily search | Implemented | Primary structured search provider |
| Search fallback | Optional | Bocha when keyed; public DuckDuckGo/Bing when Tavily is unconfigured, with visible provenance |
| Public webpage reading | Implemented | SSRF, redirect, timeout, type, and size protections |
| OpenAI, Anthropic, DashScope | Implemented | Selects configured providers; Ollama adapter remains available |
| Live Slack/Discord/Feishu verification | Environment-dependent | Requires credentials and external app setup |

Google Workspace, Gmail, Google Drive, Microsoft 365, Outlook, and Teams are not included.

## Requirements

- Python 3.11+
- Node.js 20+ and pnpm
- One supported model provider key for real model output
- Tavily key for web search

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cd frontend && pnpm install && cd ..
cp .env.example .env
```

## Minimum configuration

Set one model key in `.env`, for example `OPENAI_API_KEY`. Optional channel credentials are not
required for WebChat. State defaults to `.muxtrail-state`, which is ignored by Git.

## WebChat quick start

Terminal 1:

```bash
source .venv/bin/activate
muxtrail gateway run --host 127.0.0.1 --port 18789
```

Terminal 2:

```bash
cd frontend
pnpm dev --host 127.0.0.1 --port 3001
```

Open `http://127.0.0.1:3001`. Send a message and inspect the execution path, runtime timeline,
model context, tool arguments/results, final response, and delivery status.

## Channel setup

- [Slack Socket Mode setup](docs/slack-setup.md)
- [Discord Gateway setup](docs/discord-setup.md)
- [Optional Feishu setup](docs/feishu-optional.md)

Each external channel is opt-in with `MUXTRAIL_<CHANNEL>_ENABLED=true` and uses the shared
Gateway; no channel adapter calls a model provider directly.

## Tavily setup

Set `TAVILY_API_KEY`. The `web_search` tool returns structured evidence: title, URL, excerpt,
score, rank, provider metadata, timing, retry count, and domain filters. Research flows should
search, inspect results, fetch important sources with `web_fetch`, then answer from those sources.
A zero-result search is explicitly not treated as evidence that information does not exist.
Without a Tavily key, MuxTrail may query public DuckDuckGo and Bing RSS endpoints. Results expose
`fallback_from`, `fallback_reason`, and the actual provider, so the fallback is not silent. Public
fallbacks are less reliable and may be blocked or rate-limited; use Tavily for production.

## Tests and checks

```bash
pytest -q
ruff check backend/src/muxtrail tests
mypy backend/src/muxtrail
cd frontend && pnpm build
```

Focused tests live in `tests/contract`, including mocked Slack/Discord round trips, Tavily,
webpage safety, sessions, memory history, tools, and Feishu regressions.

## Security notes

MuxTrail redacts sensitive keys before config responses, traces, and structured logs. Channel
tokens never belong in the browser or transcripts. Remote channels use the restricted `messaging`
tool profile; tool calls are allowlisted, schema-validated, time-limited, and loop-bounded.
`web_fetch` permits only public HTTP(S) destinations and validates redirect hops and resolved IPs.
See [Security and privacy](docs/security.md).

## Known limitations

- Live external-channel tests require the owner's credentials and were not run by mocked tests.
- WebChat is a local development interface, not an internet-facing multi-tenant control plane.
- Gateway authentication should be enabled before binding beyond loopback.
- Session compaction is available, but quality depends on the configured model.
- Slack and Discord adapters keep deduplication state in memory; restarts clear that cache.

## More documentation

- [Environment variables](docs/environment.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Demo script](docs/demo.md)
- [Roadmap](docs/roadmap.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT. See [LICENSE](LICENSE).
