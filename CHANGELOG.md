# Changelog

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
