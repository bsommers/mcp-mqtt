# 1. Installing

[← Back to manual](README.md) · [← Back to Project README](../../README.md)

## Contents
- [Prerequisites](#prerequisites)
- [Install](#install)
- [First run](#first-run)
- [Register with a client](#register-with-a-client)

## Prerequisites

Python >= 3.11, [uv](https://docs.astral.sh/uv/), and a reachable MQTT broker (Mosquitto, EMQX or NanoMQ). Docker is optional, for the test brokers.

## Install

```bash
git clone <this repository> mcp-mqtt && cd mcp-mqtt
uv sync
```

Console scripts installed: `mcp-mosquitto`, `mcp-emqx`, `mcp-nanomq`.

## First run

1. (Optional) start test brokers: `docker compose -f docker/docker-compose.yml up -d`
2. Run the demo client, which launches the server over stdio and exercises it:

   ```bash
   uv run python examples/03_secure_policy_demo.py --broker mosquitto
   ```

   Expected: lines starting `[DENIED ]` for each blocked request (wildcard publish, `$SYS` publish, outside allowlist, oversize, subscribe `#`, retained) followed by an injection-looking payload returned with `"untrusted": true`.
3. Register the server with your MCP client: [how-to](../how-to.md#register-with-claude-code).

## Register with a client

Claude Code: `claude mcp add ...` (see [`examples/claude_code_mcp_add.sh`](../../examples/claude_code_mcp_add.sh)). Claude Desktop: edit `claude_desktop_config.json` (see [`examples/claude_desktop_config.json`](../../examples/claude_desktop_config.json)). The server must be given at least `MQTT_PUBLISH_ALLOW` and/or `MQTT_SUBSCRIBE_ALLOW`, otherwise every call is denied.
