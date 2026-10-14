# Environment variables

| Variable | Required | Purpose |
|---|---:|---|
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DASHSCOPE_API_KEY` | One | Model provider |
| `TAVILY_API_KEY` | For search | Primary structured web search |
| `BOCHA_API_KEY` | No | Keyed fallback after Tavily; without either key, public DuckDuckGo/Bing fallback is attempted and explicitly traced |
| `MUXTRAIL_STATE_DIR` | No | State directory; defaults to `.muxtrail-state` |
| `MUXTRAIL_CONFIG_PATH` | No | Config file override |
| `MUXTRAIL_SLACK_ENABLED` | No | Enable Slack Socket Mode |
| `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` | With Slack | Slack credentials |
| `MUXTRAIL_DISCORD_ENABLED` | No | Enable Discord Gateway |
| `DISCORD_BOT_TOKEN` | With Discord | Discord bot credential |
| `MUXTRAIL_FEISHU_ENABLED` | No | Enable optional Feishu |
| `FEISHU_APP_ID`, `FEISHU_APP_SECRET` | With Feishu | Feishu credentials |

WebChat starts without optional channel credentials. Use `.env.example` as the authoritative list.
