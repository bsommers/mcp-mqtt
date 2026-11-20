# 2. Configuration reference

[← Back to manual](README.md) · [← Back to Project README](../../README.md)

All configuration is environment variables read once at startup (`src/mcp_mqtt/config.py`, `src/mcp_mqtt/brokers/*.py`). Booleans are true only when the value is exactly `1`. Integers must parse or startup fails.

## Contents
- [Connection](#connection) · [TLS](#tls) · [Authorization](#authorization) · [Limits](#limits) · [EMQX REST](#emqx-rest) · [NanoMQ REST](#nanomq-rest) · [Fixed values](#fixed-values-not-configurable)

## Connection

| Variable | Default | Meaning |
|---|---|---|
| `MQTT_HOST` | `localhost` | Broker host |
| `MQTT_PORT` | `1883`, or `8883` if `MQTT_TLS=1` | Broker port |
| `MQTT_USERNAME` | unset | Username (empty string = unset) |
| `MQTT_PASSWORD` | unset | Password; refused over plaintext unless host is `localhost`, `127.0.0.1` or `::1` |

## TLS

| Variable | Default | Meaning |
|---|---|---|
| `MQTT_TLS` | off | `1` enables TLS with certificate verification |
| `MQTT_TLS_CA` | unset | CA bundle path (else system defaults) |
| `MQTT_TLS_CERT`, `MQTT_TLS_KEY` | unset | Client certificate and key (mutual TLS) |
| `MQTT_TLS_INSECURE` | off | `1` disables certificate verification and hostname check; requires `MQTT_TLS=1` |

## Authorization

| Variable | Default | Meaning |
|---|---|---|
| `MQTT_PUBLISH_ALLOW` | empty (deny all) | Comma-separated topic patterns (`+`, `#` allowed in the pattern) that may be published to |
| `MQTT_SUBSCRIBE_ALLOW` | empty (deny all) | Comma-separated filters; a requested filter must be fully covered by one entry |
| `MQTT_READ_ONLY` | off | `1` does not register `mqtt_publish` |
| `MQTT_ALLOW_RETAIN` | off | `1` permits `retain=true` publishes |
| `MQTT_MAX_QOS` | `1` | Highest accepted QoS; clamped to 0..2 |

## Limits

| Variable | Default | Meaning |
|---|---|---|
| `MQTT_MAX_PUBLISH_BYTES` | `65536` | Max decoded publish payload |
| `MQTT_MAX_MESSAGE_BYTES` | `8192` | Max bytes of each inbound message returned (rest truncated) |
| `MQTT_MAX_MESSAGES` | `100` | Max messages per subscribe/retained/sys call |
| `MQTT_MAX_RESPONSE_BYTES` | `32768` | Total response budget; also the REST helper body cap |
| `MQTT_RATE_LIMIT_PER_MINUTE` | `60` | Token bucket size and refill per minute, shared by all tools in the process |

The five limits must be >= 1 or startup fails.

## EMQX REST

Read by `mcp-emqx` only.

| Variable | Default | Meaning |
|---|---|---|
| `EMQX_API_URL` | `http://localhost:18083` | Base URL (http/https only) |
| `EMQX_API_KEY` | unset | API key (used as basic-auth user) |
| `EMQX_API_SECRET` | unset | API secret; both required or tools return an error |

## NanoMQ REST

Read by `mcp-nanomq` only.

| Variable | Default | Meaning |
|---|---|---|
| `NANOMQ_API_URL` | `http://localhost:8081` | Base URL (http/https only) |
| `NANOMQ_API_USER` | unset | Basic-auth user |
| `NANOMQ_API_PASSWORD` | unset | Basic-auth password; both required |

## Fixed values (not configurable)

`max_wait_seconds` 30; `max_topic_length` 256 bytes; `max_topic_levels` 16; client id `mcp-mqtt-<8 hex>`; MQTT keepalive 30 s; connect timeout 5 s; publish ack timeout 10 s; REST timeout 5 s and `limit` capped at 100.

## Allowlist semantics

Publish: pattern match of a concrete topic (no `+`/`#`/`$` in the topic). Subscribe: coverage. See [how-to](../how-to.md#allowlist-patterns) for a table.
