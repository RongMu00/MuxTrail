# Security and privacy

- Secrets are loaded server-side and recursively redacted from config responses, traces, and logs.
- `.env`, state, virtual environments, dependencies, caches, builds, logs, and editor files are
  excluded from Git.
- Remote channel events use a restricted tool profile. Tools are allowlisted, argument-validated,
  time-limited, output-bounded, and subject to a maximum model/tool loop count.
- Slack and Discord filter bot/self events, deduplicate retries, bound reconnect delays, and surface
  delivery errors.
- Web fetching rejects non-HTTP(S), local hostnames, non-public literal or resolved IPs, unsafe
  redirect hops, excessive redirects, unsupported content, and oversized responses.
- Never bind the Gateway publicly without authentication and a trusted reverse proxy.
- Local transcript/state files may contain conversation content. Protect the workstation and remove
  state deliberately when it is no longer needed.
