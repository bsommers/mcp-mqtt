"""Shared helpers for the example clients (not an MCP server: printing is fine here)."""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PORTS = {"mosquitto": 21883, "emqx": 21884, "nanomq": 21885}


def parse_args(desc: str) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument("--broker", choices=PORTS, default="mosquitto")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=None, help="default: test-compose port for the broker")
    return ap.parse_args()


@asynccontextmanager
async def server(args: argparse.Namespace, **env: str):
    base = {
        "MQTT_HOST": args.host,
        "MQTT_PORT": str(args.port or PORTS[args.broker]),
        "MQTT_PUBLISH_ALLOW": "demo/#",
        "MQTT_SUBSCRIBE_ALLOW": "demo/#",
    }
    base.update(env)
    params = StdioServerParameters(
        command=sys.executable, args=["-m", f"mcp_mqtt.brokers.{args.broker}"], env=base)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            yield s


async def call(s: ClientSession, tool: str, **kw) -> dict:
    return json.loads((await s.call_tool(tool, kw)).content[0].text)
