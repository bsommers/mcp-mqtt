"""Publish/subscribe round trip through an MCP broker server.

Run: uv run python examples/01_publish_subscribe.py --broker mosquitto
"""
import asyncio

from _common import call, parse_args, server


async def main() -> None:
    args = parse_args(__doc__)
    async with server(args) as s, server(args) as p:
        print("tools:", [t.name for t in (await s.list_tools()).tools])
        print("policy:", await call(s, "mqtt_policy"))
        sub = asyncio.create_task(call(s, "mqtt_subscribe", topic_filter="demo/hello", max_messages=1, wait_seconds=8))
        await asyncio.sleep(1.5)
        print("publish:", await call(p, "mqtt_publish", topic="demo/hello", payload="hi from MCP"))
        print("received:", await sub)


asyncio.run(main())
