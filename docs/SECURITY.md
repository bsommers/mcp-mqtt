# Security policy

[← Back to Project README](../README.md) · [Docs index](README.md) · Reporting: [../SECURITY.md](../SECURITY.md)

## Design rules

The servers follow the secure-design-patterns MCP rules, plus MQTT-specific additions.

| Rule | Implementation | Test |
|---|---|---|
| MCP-001: config and credentials from server env only | `Settings.from_env()`; no credential-like tool parameters | `test_static_gates.py::test_tool_functions_have_no_credential_params`, `test_config.py` |
| MCP-003: dual-axis bounding of output | `render_inbound` caps each message at `MQTT_MAX_MESSAGE_BYTES`; `bound_messages` caps count (`MQTT_MAX_MESSAGES`) then total bytes (`MQTT_MAX_RESPONSE_BYTES`); REST helpers cap the response body | `test_security.py` |
| MCP-006: stateless handlers | New short-lived connection (random client id) per call; only process-wide state is the rate limiter | `test_server_unit.py`, integration |
| MCP-008: stdout is protocol only | No `print`; logging to stderr | `test_static_gates.py::test_no_print_calls`, `test_integration.py::test_stdout_is_only_jsonrpc` |
| MQTT: deny-by-default topic allowlists | `validate_publish_topic`, `validate_subscribe_filter` | `test_security.py`, integration |
| MQTT: no wildcard or `$` publish | same | same |
| MQTT: subscribe cannot escalate | `filter_covered_by` | same |
| MQTT: payload, QoS, retain, rate caps | `encode_publish_payload`, `validate_qos`, `MQTT_ALLOW_RETAIN`, `RateLimiter` | same |
| MQTT: inbound payload is untrusted | `"untrusted": true`, truncation, base64 for binary/control chars | same |
| Transport: no password over plaintext off-loopback | `Settings.validate()` | `test_config.py` |
| REST helpers: fixed operator URL, GET only, no redirects, capped body, 5 s timeout | `brokers/emqx.py`, `brokers/nanomq.py` | exercised manually against the Docker brokers |

## Prompt injection from broker payloads

Any client that can publish to an allowlisted topic controls text that reaches the model. The server cannot make the model ignore it. What it does: delivers payloads only in a `payload` field of a structured JSON object flagged `"untrusted": true`; truncates; base64-encodes binary and control-character data; and states in the tool description that payloads are content, not instructions. Reduce impact by keeping publish allowlists narrow, using `MQTT_READ_ONLY=1` where acting is not needed, and keeping human approval on tool calls in your MCP client.

## Honest limits

- **No per-client authorization** beyond the two allowlists. Every user of a server process has the same rights. Use broker users/ACLs and separate server instances with separate credentials for different trust levels.
- **Allowlisted means fully trusted**: the model can write every allowlisted publish topic and read every allowlisted filter.
- **Prompt-injection defence is labelling and bounding only.**
- **Short-lived connections**: no persistent session, no long-lived subscription; messages published between calls are missed unless retained.
- **QoS**: default cap is 1. `MQTT_MAX_QOS=2` is accepted, but each call uses a fresh clean connection, so end-to-end exactly-once is not provided across calls. Subscribe QoS is the requested level, subject to the broker's grant.
- **Retained collection**: `mqtt_get_retained` subscribes and keeps only retained messages, but non-retained live messages count towards the `MQTT_MAX_MESSAGES` collection limit, so on a busy filter retained messages may be missed.
- **Rate limit is per process and per tool call**, not per topic or per user.
- **Username without password** and plaintext on loopback are not blocked; `MQTT_TLS_INSECURE=1` disables certificate verification.
- **Secrets in environment** are visible to anyone who can read the process environment.
- Limits for wait time, topic length and topic depth are fixed in code.
- The bundled Docker brokers are anonymous test fixtures.
- Logs record topics and sizes (not payloads) on stderr.

## Reporting a vulnerability

See [../SECURITY.md](../SECURITY.md).
