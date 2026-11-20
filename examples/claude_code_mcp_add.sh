#!/usr/bin/env bash
# Register all three servers with Claude Code. Set REPO to this checkout.
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"

claude mcp add mosquitto \
  -e MQTT_HOST=localhost -e MQTT_PORT=1883 \
  -e MQTT_PUBLISH_ALLOW='home/commands/#' -e MQTT_SUBSCRIBE_ALLOW='home/#,$SYS/#' \
  -- uv run --directory "$REPO" mcp-mosquitto

claude mcp add emqx \
  -e MQTT_HOST=localhost -e MQTT_PORT=1883 \
  -e MQTT_PUBLISH_ALLOW='home/commands/#' -e MQTT_SUBSCRIBE_ALLOW='home/#' \
  -- uv run --directory "$REPO" mcp-emqx

claude mcp add nanomq \
  -e MQTT_HOST=localhost -e MQTT_PORT=1883 \
  -e MQTT_PUBLISH_ALLOW='home/commands/#' -e MQTT_SUBSCRIBE_ALLOW='home/#' \
  -- uv run --directory "$REPO" mcp-nanomq
