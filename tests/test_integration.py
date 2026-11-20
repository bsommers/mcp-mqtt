"""End-to-end tests: spawn the real server over stdio against live brokers."""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import uuid
from contextlib import asynccontextmanager

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.integration

PORTS = {"mosquitto": 21883, "emqx": 21884, "nanomq": 21885}
BROKERS = list(PORTS)


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(params=BROKERS)
def broker(request):
    name = request.param
    if not _port_open(PORTS[name]):
        pytest.skip(f"{name} broker not listening on {PORTS[name]}")
    return name


def _env(broker: str, **extra: str) -> dict[str, str]:
    env = {
        "MQTT_HOST": "127.0.0.1",
        "MQTT_PORT": str(PORTS[broker]),
        "MQTT_PUBLISH_ALLOW": "test/#",
        "MQTT_SUBSCRIBE_ALLOW": "test/#",
    }
    env.update(extra)
    return env


@asynccontextmanager
async def open_session(broker: str, **extra: str):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", f"mcp_mqtt.brokers.{broker}"], env=_env(broker, **extra)
    )
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            yield session


async def call(session: ClientSession, tool: str, **args) -> dict:
    res = await session.call_tool(tool, args)
    return json.loads(res.content[0].text)


def _topic() -> str:
    return f"test/{uuid.uuid4().hex[:8]}"


def test_stdout_is_only_jsonrpc(broker):
    env = {**os.environ, **_env(broker)}
    p = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", f"mcp_mqtt.brokers.{broker}"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True,
    )
    lines = []
    try:
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        p.stdin.write("".join(json.dumps(m) + "\n" for m in msgs))
        p.stdin.flush()
        while len(lines) < 2:  # read both responses, then close
            ln = p.stdout.readline()
            assert ln, "server closed stdout early"
            lines.append(ln)
    finally:
        p.kill()
    for ln in lines:
        assert json.loads(ln)["jsonrpc"] == "2.0"


async def test_handshake_and_tools(broker):
    async with open_session(broker) as s:
        names = {t.name for t in (await s.list_tools()).tools}
    assert {"mqtt_publish", "mqtt_subscribe", "mqtt_get_retained", "mqtt_policy"} <= names
    if broker == "mosquitto":
        assert "mosquitto_sys_stats" in names


async def test_publish_subscribe_roundtrip(broker):
    topic = _topic()
    # Two server processes: tool handlers are synchronous, so a blocking subscribe would
    # otherwise delay a publish sent over the same session.
    async with open_session(broker) as s, open_session(broker) as p:
        sub = asyncio.create_task(call(s, "mqtt_subscribe", topic_filter=topic, max_messages=1, wait_seconds=8))
        await asyncio.sleep(1.5)
        pub = await call(p, "mqtt_publish", topic=topic, payload="hello")
        assert pub["ok"], pub
        got = await sub
    assert got["ok"] and got["count"] == 1, got
    m = got["messages"][0]
    assert m["payload"] == "hello" and m["topic"] == topic and m["untrusted"] is True


async def test_retained(broker):
    topic = _topic()
    async with open_session(broker, MQTT_ALLOW_RETAIN="1") as s:
        pub = await call(s, "mqtt_publish", topic=topic, payload="kept", retain=True)
        assert pub["ok"], pub
        got = await call(s, "mqtt_get_retained", topic_filter=topic, wait_seconds=3)
        # cleanup retained message
        await call(s, "mqtt_publish", topic=topic, payload="", retain=True)
    assert got["ok"] and got["count"] == 1, got
    assert got["messages"][0]["payload"] == "kept" and got["messages"][0]["retained"] is True


async def test_retain_disabled_by_default(broker):
    async with open_session(broker) as s:
        r = await call(s, "mqtt_publish", topic=_topic(), payload="x", retain=True)
    assert not r["ok"]


async def test_denied_topic_outside_allowlist(broker):
    async with open_session(broker) as s:
        r = await call(s, "mqtt_publish", topic="other/thing", payload="x")
    assert not r["ok"] and "MQTT_PUBLISH_ALLOW" in r["error"]


async def test_oversize_payload_rejected(broker):
    async with open_session(broker, MQTT_MAX_PUBLISH_BYTES="100") as s:
        r = await call(s, "mqtt_publish", topic=_topic(), payload="a" * 101)
    assert not r["ok"] and "exceeds" in r["error"]


async def test_wildcard_publish_rejected(broker):
    async with open_session(broker) as s:
        r1 = await call(s, "mqtt_publish", topic="test/#", payload="x")
        r2 = await call(s, "mqtt_publish", topic="test/+/a", payload="x")
    assert not r1["ok"] and not r2["ok"]


async def test_subscribe_escalation_rejected(broker):
    async with open_session(broker) as s:
        r1 = await call(s, "mqtt_subscribe", topic_filter="#", wait_seconds=0.5)
        r2 = await call(s, "mqtt_subscribe", topic_filter="$SYS/#", wait_seconds=0.5)
    assert not r1["ok"] and not r2["ok"]


async def test_rate_limit(broker):
    async with open_session(broker, MQTT_RATE_LIMIT_PER_MINUTE="3") as s:
        results = [await call(s, "mqtt_publish", topic=_topic(), payload="x") for _ in range(5)]
    assert [r["ok"] for r in results[:3]] == [True] * 3, results
    assert not results[3]["ok"] and "rate limit" in results[3]["error"]


async def test_mosquitto_sys_stats():
    if not _port_open(PORTS["mosquitto"]):
        pytest.skip("mosquitto not up")
    async with open_session("mosquitto", MQTT_SUBSCRIBE_ALLOW="test/#,$SYS/#") as s:
        r = await call(s, "mosquitto_sys_stats", wait_seconds=5)
    assert r["ok"], r
    assert r["count"] > 0
