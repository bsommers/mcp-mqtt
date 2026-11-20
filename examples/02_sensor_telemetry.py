"""Simulated sensor publishes JSON every second; an 'agent' subscribes and summarizes.

Run: uv run python examples/02_sensor_telemetry.py --broker emqx --samples 5
"""
import asyncio
import json
import random
import statistics

from _common import call, parse_args, server

TOPIC = "demo/sensors/room1/temp"


async def sensor(s, n: int) -> None:
    await asyncio.sleep(1.5)  # let the subscriber attach
    for i in range(n):
        reading = {"seq": i, "celsius": round(random.uniform(19, 25), 2)}  # noqa: S311
        await call(s, "mqtt_publish", topic=TOPIC, payload=json.dumps(reading))
        await asyncio.sleep(1)


async def agent(s, n: int) -> None:
    res = await call(s, "mqtt_subscribe", topic_filter="demo/sensors/+/temp",
                     max_messages=n, wait_seconds=n + 5)
    vals = [json.loads(m["payload"])["celsius"] for m in res["messages"] if m["encoding"] == "utf8"]
    if vals:
        print(f"agent summary: n={len(vals)} min={min(vals)} max={max(vals)} mean={statistics.mean(vals):.2f}")
    else:
        print("agent: no readings", res)


async def run() -> None:
    import sys
    samples = 5
    if "--samples" in sys.argv:
        i = sys.argv.index("--samples")
        samples = int(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    args = parse_args(__doc__)
    # separate server processes so the publisher and subscriber do not share a rate limiter
    async with server(args) as pub, server(args) as sub:
        await asyncio.gather(sensor(pub, samples), agent(sub, samples))


asyncio.run(run())
