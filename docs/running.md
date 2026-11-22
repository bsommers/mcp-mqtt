# Running

[← Back to Project README](../README.md) · [Docs index](README.md)

## Prerequisites

- Python >= 3.11 and [uv](https://docs.astral.sh/uv/)
- An MQTT broker you can reach (Mosquitto, EMQX or NanoMQ); Docker for the bundled test brokers
- An MCP client (Claude Code, Claude Desktop, or any stdio MCP client)

## Install

```bash
git clone <this repository> mcp-mqtt && cd mcp-mqtt
uv sync                  # add --extra emqx or --extra nanomq for the REST tools
```

This installs three console scripts (from `pyproject.toml`): `mcp-mosquitto`, `mcp-emqx`, `mcp-nanomq`. Each can also be started as `python -m mcp_mqtt.brokers.<mosquitto|emqx|nanomq>`.

## Start a server

The server speaks MCP over stdio; normally your MCP client launches it. To run it by hand:

```bash
MQTT_HOST=localhost \
MQTT_PUBLISH_ALLOW='home/cmd/#' \
MQTT_SUBSCRIBE_ALLOW='home/#' \
uv run mcp-mosquitto
```

It then waits on stdin for JSON-RPC. Logs are JSON lines on stderr. With no allowlists set, the server starts but every publish/subscribe is denied.

## Startup validation

`Settings.from_env()` fails fast with a `ValueError` (exit with traceback on stderr) for:

| Condition | Message |
|---|---|
| non-integer numeric var | `MQTT_PORT must be an integer` (name varies) |
| `MQTT_TLS_INSECURE=1` without `MQTT_TLS=1` | `MQTT_TLS_INSECURE requires MQTT_TLS=1` |
| password set, no TLS, host not `localhost`/`127.0.0.1`/`::1` | `refusing to send credentials over plaintext to a non-loopback host; set MQTT_TLS=1` |
| any of the byte/count/topic/rate limits < 1 | `limits must be >= 1` |
| unrecognised value for a boolean switch | `MQTT_READ_ONLY must be one of 1/true/yes/on or 0/false/no/off` (name varies) |
| port outside 1..65535 | `MQTT_PORT must be 1..65535` |
| `MQTT_MAX_MESSAGE_BYTES` > `MQTT_MAX_RESPONSE_BYTES` | `MQTT_MAX_MESSAGE_BYTES must be <= MQTT_MAX_RESPONSE_BYTES` |

There is no CLI flag surface: all configuration is environment variables. See the [configuration reference](usermanual/02-configuration-reference.md) for every variable.

## Registering with a client

See [how-to.md](how-to.md#register-with-claude-code) and the files [`examples/claude_code_mcp_add.sh`](../examples/claude_code_mcp_add.sh) and [`examples/claude_desktop_config.json`](../examples/claude_desktop_config.json).

## Local test brokers

```bash
docker compose -f docker/docker-compose.yml up -d
```

Anonymous, loopback only: Mosquitto `127.0.0.1:21883`, EMQX `127.0.0.1:21884` (API `18083`), NanoMQ `127.0.0.1:21885` (API `8081`). See [`docker/README.md`](../docker/README.md) for the test-only API credentials.

## Example clients

```bash
uv run python examples/01_publish_subscribe.py --broker mosquitto
uv run python examples/02_sensor_telemetry.py  --broker emqx
uv run python examples/03_secure_policy_demo.py --broker nanomq
```

Each takes `--broker {mosquitto,emqx,nanomq}`, `--host` (default `127.0.0.1`) and `--port` (default: the compose port). They spawn the server over stdio with `MQTT_PUBLISH_ALLOW`/`MQTT_SUBSCRIBE_ALLOW` set to `demo/#`.

## Exit behaviour

The server exits when stdin closes (client disconnect). Configuration errors exit non-zero with a Python traceback on stderr. Tool-level failures never exit the process: they return `{"ok": false, "error": "..."}`.
