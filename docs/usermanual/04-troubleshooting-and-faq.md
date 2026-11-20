# 4. Troubleshooting and FAQ

[← Back to manual](README.md) · [← Back to Project README](../../README.md)

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Every call returns "not permitted" | Allowlists empty (deny by default) | Set `MQTT_PUBLISH_ALLOW` / `MQTT_SUBSCRIBE_ALLOW` in the server's env block |
| Server exits at start with `ValueError` | Invalid config | See [startup validation](../running.md#startup-validation) |
| `refusing to send credentials over plaintext...` | Password with non-loopback host and no TLS | Set `MQTT_TLS=1` |
| `cannot reach broker: ConnectionRefusedError` | Wrong host/port, broker down | Check `MQTT_HOST`/`MQTT_PORT` (TLS defaults to 8883) |
| `broker connection failed: ...` | Bad credentials, TLS handshake, broker ACL | Check broker logs, CA file, user/password |
| Subscribe returns `count: 0` | Nothing published during the wait window | Raise `wait_seconds` (max 30) or use `mqtt_get_retained` for retained state |
| `mosquitto_sys_stats` denied | `$SYS/#` not allowlisted | Add `$SYS/#` to `MQTT_SUBSCRIBE_ALLOW` |
| EMQX/NanoMQ tool says "not configured" | REST credentials missing | Set `EMQX_API_KEY`/`EMQX_API_SECRET` or `NANOMQ_API_USER`/`NANOMQ_API_PASSWORD` |
| `HTTP 401` from REST helper | Wrong API credentials | Regenerate key / check `nanomq.conf` |
| `API request failed: ConnectError` | Wrong `*_API_URL` | Fix the URL |
| `mqtt_publish` missing from tool list | `MQTT_READ_ONLY=1` | Unset it |
| Client shows server failing to parse | Something wrote to stdout | Do not wrap the command in a script that prints; logs belong on stderr |
| Integration tests all skipped | Docker brokers not running | `docker compose -f docker/docker-compose.yml up -d` |

## FAQ

**Can the model change the allowlist?** No. Policy is server environment only; no tool accepts policy or credentials.

**Does a blocking subscribe stall other calls?** No. Handlers are async and run broker I/O in worker threads (`asyncio.to_thread`), so a publish can proceed while a subscribe waits. (Older notes recommending two server processes no longer apply.) The EMQX/NanoMQ REST helpers are synchronous and block for up to their 5 s timeout.

**Why do I miss messages between calls?** Connections are short-lived; there is no persistent session. Use retained messages for state.

**Is QoS 2 supported?** Accepted when `MQTT_MAX_QOS=2`, but there is no cross-call exactly-once guarantee.

**Are payloads safe to act on?** No. They are flagged `untrusted`; see [SECURITY](../SECURITY.md).

**Can I use it for high-volume streams?** No; see [when not to use it](../purpose.md#when-not-to-use-it).
