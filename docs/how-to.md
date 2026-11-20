# How-to recipes

[← Back to Project README](../README.md) · [Docs index](README.md)

## Contents
- [Register with Claude Code](#register-with-claude-code)
- [Register with Claude Desktop](#register-with-claude-desktop)
- [Per-broker setup](#per-broker-setup)
- [TLS and authentication](#tls-and-authentication)
- [Allowlist patterns](#allowlist-patterns)
- [Read-only mode](#read-only-mode)
- [Tune limits](#tune-limits)
- [Verify a deployment](#verify-a-deployment)

## Register with Claude Code

```bash
claude mcp add mosquitto \
  -e MQTT_HOST=localhost -e MQTT_PORT=1883 \
  -e MQTT_PUBLISH_ALLOW='home/commands/#' -e MQTT_SUBSCRIBE_ALLOW='home/#' \
  -- uv run --directory /path/to/mcp-mqtt mcp-mosquitto
```

Use `mcp-emqx` or `mcp-nanomq` for those brokers. [`examples/claude_code_mcp_add.sh`](../examples/claude_code_mcp_add.sh) registers all three (set `REPO` to the checkout). Single-quote values containing `$` (such as `$SYS/#`) so the shell does not expand them.

## Register with Claude Desktop

Add to `claude_desktop_config.json` (full sample: [`examples/claude_desktop_config.json`](../examples/claude_desktop_config.json)):

```json
{
  "mcpServers": {
    "mosquitto": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-mqtt", "mcp-mosquitto"],
      "env": {
        "MQTT_HOST": "localhost", "MQTT_PORT": "1883",
        "MQTT_PUBLISH_ALLOW": "home/commands/#",
        "MQTT_SUBSCRIBE_ALLOW": "home/#"
      }
    }
  }
}
```

Replace `/path/to/mcp-mqtt` with your checkout path.

## Per-broker setup

### Mosquitto

Entry point `mcp-mosquitto`. Extra tool `mosquitto_sys_stats` reads `$SYS/broker/#`; it works only if `MQTT_SUBSCRIBE_ALLOW` contains `$SYS/#` (or `$SYS/broker/#`). Publishing to `$SYS` is always refused.

```bash
MQTT_SUBSCRIBE_ALLOW='home/#,$SYS/#' uv run mcp-mosquitto
```

### EMQX

Entry point `mcp-emqx`. Create an API key in the dashboard (Management > API Keys), ideally read-only, and put it in the **server** environment:

```bash
EMQX_API_URL=http://localhost:18083 EMQX_API_KEY=... EMQX_API_SECRET=... \
MQTT_PUBLISH_ALLOW='home/cmd/#' MQTT_SUBSCRIBE_ALLOW='home/#' uv run mcp-emqx
```

Tools `emqx_stats`, `emqx_list_clients`, `emqx_list_subscriptions` call `/api/v5/stats`, `/clients`, `/subscriptions` (GET only). Without key and secret they return `{"ok": false, "error": "EMQX_API_KEY not configured"}`; publish/subscribe still work.

### NanoMQ

Entry point `mcp-nanomq`. Enable the HTTP API (default port 8081) in `nanomq.conf`, then:

```bash
NANOMQ_API_URL=http://localhost:8081 NANOMQ_API_USER=admin NANOMQ_API_PASSWORD=... \
MQTT_PUBLISH_ALLOW='home/cmd/#' MQTT_SUBSCRIBE_ALLOW='home/#' uv run mcp-nanomq
```

Tools `nanomq_stats` (`/api/v4/brokers`) and `nanomq_list_clients` (`/api/v4/clients`). Without credentials they return an error naming `NANOMQ_API_USER/NANOMQ_API_PASSWORD`.

## TLS and authentication

```bash
MQTT_HOST=broker.example.com MQTT_TLS=1 \
MQTT_TLS_CA=/etc/ssl/certs/my-ca.pem \
MQTT_USERNAME=agent MQTT_PASSWORD=... \
MQTT_PUBLISH_ALLOW='plant/cmd/line1' MQTT_SUBSCRIBE_ALLOW='plant/+/status' \
uv run mcp-mosquitto
```

- `MQTT_TLS=1` switches the default port to 8883 (override with `MQTT_PORT`) and requires certificate verification.
- Mutual TLS: add `MQTT_TLS_CERT` and `MQTT_TLS_KEY`.
- A password over plaintext to any host other than `localhost`/`127.0.0.1`/`::1` is refused at startup.
- `MQTT_TLS_INSECURE=1` disables certificate verification (and hostname checks); use only for throwaway testing. It requires `MQTT_TLS=1`.
- Keep secrets in the client's MCP `env` block or a secret manager, never in tool prompts.

## Allowlist patterns

Allowlists are comma-separated MQTT patterns. Publish: the concrete topic must match a pattern. Subscribe: the requested filter must be **fully covered** by a pattern.

| `MQTT_SUBSCRIBE_ALLOW` | Request | Result |
|---|---|---|
| `home/#` | `home/kitchen/temp` | allowed |
| `home/#` | `home/+/temp` | allowed |
| `home/#` | `#` | denied (broader than entry) |
| `home/+/temp` | `home/#` | denied |
| `home/+/temp` | `home/kitchen/temp` | allowed |
| `home/#` | `$SYS/#` | denied (needs an entry starting with `$`) |
| empty | anything | denied |

Publish: `MQTT_PUBLISH_ALLOW='home/commands/#'` permits `home/commands/light1` and also the parent topic `home/commands` (MQTT `#` matches the parent level); list exact topics when that matters. Wildcard (`+`, `#`) and `$`-prefixed publish topics are always rejected.

Prefer narrow, separate lists: read broadly, write narrowly.

## Read-only mode

```bash
MQTT_READ_ONLY=1 MQTT_SUBSCRIBE_ALLOW='sensors/#' uv run mcp-emqx
```

`mqtt_publish` is not registered at all, so clients do not see it (`mqtt_policy` reports `"read_only": true`). The EMQX/NanoMQ REST helpers are GET-only regardless.

## Tune limits

| Goal | Setting |
|---|---|
| Smaller model context per call | `MQTT_MAX_MESSAGE_BYTES=2048 MQTT_MAX_MESSAGES=20 MQTT_MAX_RESPONSE_BYTES=16384` |
| Slower, safer agent | `MQTT_RATE_LIMIT_PER_MINUTE=10` |
| Allow retained commands | `MQTT_ALLOW_RETAIN=1` (retained messages persist on the broker) |
| Permit QoS 2 | `MQTT_MAX_QOS=2` (clamped to 0..2) |
| Bigger publishes | `MQTT_MAX_PUBLISH_BYTES=262144` |

`max_wait_seconds` (30), `max_topic_length` (256 bytes) and `max_topic_levels` (16) are fixed in code (`Settings` defaults), not environment-configurable.

## Verify a deployment

Ask the agent to call `mqtt_policy`; it returns the active allowlists and limits without secrets. Try a denied call (for example subscribe to `#`) and confirm `{"ok": false, "error": "subscription not permitted by MQTT_SUBSCRIBE_ALLOW"}`. Or run `uv run python examples/03_secure_policy_demo.py` against the test brokers.
