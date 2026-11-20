# Purpose

[← Back to Project README](../README.md) · [Docs index](README.md)

## Why mcp-mqtt

LLM agents increasingly need to see and influence the physical and operational world, and MQTT is the common bus for IoT devices, sensors, home automation and edge systems. A safe bridge between an agent and a broker is therefore useful, but a naive one is risky. If you hand an agent a raw MQTT client it can:

- publish to any topic, including ones that actuate devices;
- subscribe to `#` and read everything on the broker;
- flood the broker, or pull unbounded payloads into the model context;
- read **attacker-controlled payloads** (anything any device or client published) as if they were instructions (prompt injection);
- be handed credentials as tool parameters, where they leak into transcripts and logs.

We built `mcp-mqtt` because we did not find a hardened MCP server for Mosquitto, EMQX and NanoMQ that addressed these points. It is a set of [MCP](https://modelcontextprotocol.io) servers (one per broker profile) with a small tool surface where every guard lives **server-side**, configured from the server's environment and never from tool inputs.

## Value proposition

| Value | How it is delivered (verifiable in code) |
|---|---|
| Deny-by-default authorization | Empty `MQTT_PUBLISH_ALLOW` / `MQTT_SUBSCRIBE_ALLOW` permit nothing; subscribe filters must be covered by an entry (`security.py`) |
| Size, count and rate bounds | Publish/message/response byte caps, message count, wait cap, topic length/depth, token-bucket rate limit (`config.py`, `security.py`) |
| Untrusted-data flagging | Every inbound message carries `"untrusted": true`, is truncated, and is base64-encoded if binary (`render_inbound`) |
| No credentials in tool inputs | Credentials come from env only; a static test rejects credential-named tool parameters |
| One consistent tool surface across three brokers | `mqtt_publish`, `mqtt_subscribe`, `mqtt_get_retained`, `mqtt_policy` are identical on Mosquitto, EMQX and NanoMQ |
| Broker-specific extras | `mosquitto_sys_stats`; `emqx_stats`, `emqx_list_clients`, `emqx_list_subscriptions`; `nanomq_stats`, `nanomq_list_clients` |
| Tested against real brokers | Integration tests run the stdio server against Dockerised Mosquitto, EMQX and NanoMQ ([TESTING.md](TESTING.md)) |

## Key use cases

| Scenario | Configuration sketch |
|---|---|
| IoT / sensor monitoring and summarisation: "summarise the last readings from the greenhouse sensors" | `MQTT_READ_ONLY=1`, `MQTT_SUBSCRIBE_ALLOW='greenhouse/+/telemetry'` |
| Ops / incident triage using broker stats: "how many clients are connected, any odd subscriptions?" | `emqx_stats`, `emqx_list_clients`, `nanomq_stats`, or `mosquitto_sys_stats` with `$SYS/#` allowed |
| Controlled device commands through one allowlisted topic: "turn off the porch light" | `MQTT_PUBLISH_ALLOW='home/commands/porch'`, low `MQTT_RATE_LIMIT_PER_MINUTE` |
| Home automation assistant | Read `home/#`, write `home/commands/#` only |
| Edge deployments on NanoMQ | `mcp-nanomq` against a lightweight edge broker, optional REST status helpers |
| Dev/test of MQTT systems: inject a message, watch the reaction | Publish and subscribe on a `test/#` namespace of a dev broker |
| Read-only observability | `MQTT_READ_ONLY=1` removes `mqtt_publish` entirely |

See [how-to.md](how-to.md) for the exact commands.

## When NOT to use it

- **Not a general message router or bridge.** It does not forward between topics or systems.
- **Not for high-throughput streaming.** Each call opens a fresh connection, collects a bounded batch (default max 100 messages, 32 KiB response) and disconnects; messages between calls are not seen.
- **Short-lived connections only**: no persistent session, no long-lived subscriptions, no push notifications to the model.
- **QoS 2 is off by default** (`MQTT_MAX_QOS=1`). It can be enabled, but delivery guarantees apply only within a single call, not across calls.
- **Not per-client authorization.** Beyond the allowlists, authorization is the broker's job (users, ACLs).
- Not a way to make prompt injection impossible: it bounds and labels untrusted data, nothing more.

## Problem summary

The risks above map to the tenets below; see [SECURITY.md](SECURITY.md) for the policy and its limits, and [architecture.md](architecture.md) for the threat model.

## Core tenets

| Tenet | Where it is enforced |
|---|---|
| Deny by default: empty allowlists permit nothing | `config.py`, `security.py` |
| Config and credentials come only from server env (MCP-001) | `config.py`; static gate rejects credential-named tool params |
| Dual-axis bounding of output: count and bytes (MCP-003) | `security.bound_messages`, `render_inbound` |
| Stateless handlers; one short-lived broker connection per call (MCP-006) | `client.py` |
| stdout carries JSON-RPC only; logs go to stderr (MCP-008) | `server._setup_logging`; no-`print` static gate |
| Inbound payloads are untrusted data | `render_inbound` sets `"untrusted": true` |

See [SECURITY.md](SECURITY.md) for the policy and its honest limits, and [architecture.md](architecture.md) for the threat model diagram.

## Provenance

The servers follow the layout of generated MCP servers (one module per broker profile plus shared core) but are hand-written, because MQTT is not described by OpenAPI. The MCP-001/003/006/008 rules come from the secure-design-patterns catalogue; the MQTT-specific guards (topic allowlists, payload caps, rate limit, untrusted-payload flagging) are additions made here.
