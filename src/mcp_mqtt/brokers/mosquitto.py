"""Mosquitto profile. Extra: broker stats via the $SYS tree (subject to subscribe allowlist)."""
from __future__ import annotations

import asyncio
import json

from mcp.server.fastmcp import FastMCP

from .. import client
from ..config import Settings
from ..security import (
    GuardError,
    RateLimiter,
    bound_messages,
    render_inbound,
    validate_subscribe_filter,
)
from ..server import run


def extras(mcp: FastMCP, settings: Settings, limiter: RateLimiter) -> None:
    @mcp.tool()
    async def mosquitto_sys_stats(wait_seconds: float = 3.0) -> str:
        """Read Mosquitto broker statistics from $SYS/broker/#. Requires '$SYS/#' (or narrower)
        in MQTT_SUBSCRIBE_ALLOW."""
        try:
            limiter.check()
            f = validate_subscribe_filter("$SYS/broker/#", settings)
            raw = await asyncio.to_thread(client.collect, settings, f, 0, settings.max_messages,
                                          max(0.1, min(wait_seconds, settings.max_wait_seconds)))
            msgs = [render_inbound(m.topic, m.payload, settings, m.retained, m.qos, m.size) for m in raw]
            out, cut = bound_messages(msgs, settings)
            return json.dumps({"ok": True, "count": len(out), "truncated": cut, "stats": out})
        except (GuardError, client.BrokerError) as exc:
            return json.dumps({"ok": False, "error": str(exc)})


def main() -> None:
    run("mosquitto-mqtt", extras)


if __name__ == "__main__":
    main()
