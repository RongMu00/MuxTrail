# Restricted public demo

MuxTrail keeps the owner workbench and public demo on separate security boundaries.

## Endpoints

- `https://api.muxtrail.com/*` remains protected by the Cloudflare Access owner policy.
- `wss://demo-api.muxtrail.com/demo/ws` is the only public backend route.
- The public WebSocket exposes only `demo.send` and `demo.reset`. It cannot call configuration,
  session administration, channel, model, or tool-management methods.

Each WebSocket connection receives a random temporary session. The transcript and session record
are deleted when the connection closes. Runtime events for the demo connection are sent directly
to that visitor and the visitor is never added to the privileged broadcast pool.

## Backend limits

Enable the endpoint explicitly in the service environment:

```dotenv
MUXTRAIL_DEMO_ENABLED=true
MUXTRAIL_DEMO_PUBLIC_HOST=demo-api.muxtrail.com
MUXTRAIL_ALLOWED_ORIGINS=https://app.muxtrail.com
MUXTRAIL_DEMO_MAX_MESSAGE_CHARS=1000
MUXTRAIL_DEMO_MAX_TURNS=5
MUXTRAIL_DEMO_MESSAGES_PER_HOUR=10
MUXTRAIL_DEMO_DAILY_MESSAGE_LIMIT=100
MUXTRAIL_DEMO_MAX_CONCURRENT=2
MUXTRAIL_DEMO_TIMEOUT_SECONDS=60
```

The demo agent can use only `web_search` and `web_fetch`. It has no filesystem, shell, code-editing,
session-management, Slack, Discord, or Feishu capabilities. `web_fetch` also rejects private,
loopback, link-local, reserved, and multicast destinations.

The in-memory quotas reset when the backend restarts. For production abuse prevention, add a
Cloudflare rate-limiting rule in front of the application as a second layer.

## Cloudflare setup

1. Add a public hostname to the existing tunnel:
   - Hostname: `demo-api.muxtrail.com`
   - Service: `http://127.0.0.1:18789`
2. Keep the existing owner Access application for `api.muxtrail.com` unchanged.
3. Do not create a broad bypass for `api.muxtrail.com`.
4. If a Cloudflare Access application covers the whole zone, create the narrower application
   `demo-api.muxtrail.com/demo/*` with a Bypass policy. No other demo hostname path should bypass
   Access.
5. Add a rate-limiting rule for the WebSocket handshake path `/demo/ws`. The application-level
   quota still controls completed messages after a connection is open.

The backend also enforces the hostname boundary: every HTTP endpoint and the owner `/ws` endpoint
return a denial on `demo-api.muxtrail.com`. Only `/demo/ws` accepts connections there. This is a
defense-in-depth control in case the Cloudflare rule is accidentally broadened.

After the hostname works, add the GitHub repository Actions variable
`PUBLIC_DEMO_WS_URL=wss://demo-api.muxtrail.com/demo/ws`, then run the production deployment again.
When this variable is absent, the frontend stays in owner mode, which makes the rollout fail-safe.
When it is present, the production build defaults to demo mode. `https://app.muxtrail.com/?owner=1`
switches to the Access-protected owner workbench.
