# Changelog

## Unreleased

### Changed (behavior)
- **Boolean env switches are strict.** `MQTT_TLS`, `MQTT_TLS_INSECURE`, `MQTT_READ_ONLY`, `MQTT_ALLOW_RETAIN` accept `1/true/yes/on` and `0/false/no/off`/empty (case-insensitive); anything else is a startup error. Previously only the literal `1` was true, so `MQTT_READ_ONLY=true` silently left publishing enabled.
- `httpx` is now an optional dependency: `pip install 'mcp-mqtt[emqx]'` / `'[nanomq]'` (capped `<1`). `mcp-mosquitto` no longer needs it.
- EMQX/NanoMQ REST tools are async, share one helper (`brokers/_rest.py`), refuse cleartext `http://` to non-loopback hosts, and wrap results as `{"untrusted": true, ...}` with bounded strings, lists and depth.
- `mqtt_get_retained` collects only retained messages and ends at the first live message or after a 0.5 s quiet period.
- Inbound `bytes` is the true message size; truncation cuts on a UTF-8 boundary (no spurious base64 fallback).
- Log lines are produced by a real JSON formatter (quotes/newlines escaped).

### Added
- Env vars `MQTT_MAX_WAIT_SECONDS`, `MQTT_MAX_TOPIC_LENGTH`, `MQTT_MAX_TOPIC_LEVELS`; `mqtt_policy` reports all limits.
- Startup validation: port range, `MQTT_MAX_MESSAGE_BYTES <= MQTT_MAX_RESPONSE_BYTES`, wait range; warnings for `MQTT_TLS_INSECURE` and clamped `MQTT_MAX_QOS`.
- TLS/connect failures raise a generic `BrokerError` (no filesystem paths) and the connection is always closed.
- `.github/workflows/ci.yml` (ruff, mypy --strict, coverage gate 85%, pip-audit, integration job), package metadata, `py.typed`, `scripts/update_counts.py`.
- Unit tests for `client.py` (fake paho) and REST helpers (`httpx.MockTransport`); unit coverage about 98%.

### Fixed
- `mosquitto_sys_stats` clamps `wait_seconds` from below; `mypy --strict` is clean.

## 0.1.0

### Added
- MCP servers `mcp-mosquitto`, `mcp-emqx`, `mcp-nanomq` with shared tools `mqtt_publish`, `mqtt_subscribe`, `mqtt_get_retained`, `mqtt_policy`.
- Broker extras: `mosquitto_sys_stats`; `emqx_stats`, `emqx_list_clients`, `emqx_list_subscriptions`; `nanomq_stats`, `nanomq_list_clients`.
- Deny-by-default publish/subscribe allowlists, read-only mode, retain opt-in, QoS cap, payload/message/response/rate limits, TLS options, untrusted-payload flagging.
- Async tool handlers (blocking broker I/O via `asyncio.to_thread`).
- Unit, static-gate and Docker-broker integration tests; example clients; documentation suite.

### Verification
- `uv run pytest` with the three Docker brokers up: 269 passed; `uv run pytest -m "not integration"`: 243 passed.
- `uv run mypy src`: no issues.
