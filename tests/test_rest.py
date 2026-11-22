"""REST helpers (EMQX/NanoMQ) with httpx.MockTransport: no network."""
import importlib
import json
import sys

import httpx
import pytest

from mcp_mqtt.brokers import _rest, emqx, nanomq
from mcp_mqtt.config import Settings
from mcp_mqtt.security import RateLimiter
from mcp_mqtt.server import build_server

EM = emqx.PROFILE
NA = nanomq.PROFILE


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for k in ("EMQX_API_URL", "EMQX_API_KEY", "EMQX_API_SECRET", "NANOMQ_API_URL",
              "NANOMQ_API_USER", "NANOMQ_API_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("EMQX_API_KEY", "k")
    monkeypatch.setenv("EMQX_API_SECRET", "s")
    monkeypatch.setenv("NANOMQ_API_USER", "u")
    monkeypatch.setenv("NANOMQ_API_PASSWORD", "p")


def mock(monkeypatch, handler):
    monkeypatch.setattr(_rest, "_transport", httpx.MockTransport(handler))


def get(path="/x", profile=EM, **kw):
    return json.loads(_rest.rest_get(Settings(**kw), RateLimiter(60), profile, path))


def test_ok_json_flagged_untrusted(monkeypatch):
    seen = {}

    def h(req):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["authorization"]
        return httpx.Response(200, json={"data": [{"clientid": "c1"}]})

    mock(monkeypatch, h)
    r = get("/api/v5/clients?limit=5")
    assert r == {"ok": True, "untrusted": True, "truncated": False, "data": {"data": [{"clientid": "c1"}]}}
    assert seen["url"] == "http://localhost:18083/api/v5/clients?limit=5"
    assert seen["auth"].startswith("Basic ")


def test_non_json_body_returned_as_text(monkeypatch):
    mock(monkeypatch, lambda req: httpx.Response(200, content=b"plain text"))
    assert get()["data"] == "plain text"


def test_non_200(monkeypatch):
    mock(monkeypatch, lambda req: httpx.Response(401))
    assert get() == {"ok": False, "error": "HTTP 401"}


def test_redirect_not_followed(monkeypatch):
    mock(monkeypatch, lambda req: httpx.Response(302, headers={"location": "http://evil/"}))
    assert get()["error"] == "HTTP 302"


def test_truncation_at_cap(monkeypatch):
    mock(monkeypatch, lambda req: httpx.Response(200, content=b"a" * 5000))
    r = get(max_response_bytes=1000, max_message_bytes=100)
    assert r["truncated"] is True and r["untrusted"] is True
    assert len(r["data"]) <= 256 + len("...[truncated]")


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("EMQX_API_SECRET")
    assert "not configured" in get()["error"]
    monkeypatch.delenv("NANOMQ_API_USER")
    assert "NANOMQ_API_USER" in get(profile=NA)["error"]


def test_missing_msg_single_var():
    assert _rest.RestProfile("x", "U", "http://h", "S", "S").missing_msg == "S not configured"


@pytest.mark.parametrize("url", ["ftp://localhost", "localhost:18083", "http://", "file:///etc/passwd"])
def test_bad_url_scheme(monkeypatch, url):
    monkeypatch.setenv("EMQX_API_URL", url)
    assert "http(s) URL" in get()["error"]


def test_cleartext_credentials_to_remote_refused(monkeypatch):
    monkeypatch.setenv("EMQX_API_URL", "http://emqx.example.com:18083")
    mock(monkeypatch, lambda req: pytest.fail("must not send"))
    assert "plaintext" in get()["error"]


@pytest.mark.parametrize("url", ["http://127.0.0.1:1", "http://localhost:1", "http://[::1]:1",
                                 "https://emqx.example.com"])
def test_loopback_http_and_remote_https_allowed(monkeypatch, url):
    monkeypatch.setenv("EMQX_API_URL", url)
    mock(monkeypatch, lambda req: httpx.Response(200, json={}))
    assert get()["ok"] is True


def test_base_url_without_credentials_allows_remote_http(monkeypatch):
    monkeypatch.setenv("EMQX_API_URL", "http://emqx.example.com")
    assert _rest.base_url(EM, has_credentials=False) == "http://emqx.example.com"


def test_http_error_is_generic(monkeypatch):
    def h(req):
        raise httpx.ConnectError("secret-host.internal refused")

    mock(monkeypatch, h)
    r = get()
    assert r == {"ok": False, "error": "API request failed: ConnectError"}


def test_rate_limit(monkeypatch):
    mock(monkeypatch, lambda req: httpx.Response(200, json={}))
    rl = RateLimiter(1)
    s = Settings()
    assert json.loads(_rest.rest_get(s, rl, EM, "/x"))["ok"] is True
    assert "rate limit" in json.loads(_rest.rest_get(s, rl, EM, "/x"))["error"]


def test_sanitize_bounds_untrusted_fields():
    out = _rest.sanitize({"clientid": "A" * 1000, "n": 5, "items": list(range(500))})
    assert out["clientid"].endswith("...[truncated]") and len(out["clientid"]) < 300
    assert out["n"] == 5 and len(out["items"]) == _rest.MAX_LIST_ITEMS


def test_sanitize_depth_and_keys():
    deep = cur = {}
    for _ in range(20):
        cur["a"] = {}
        cur = cur["a"]
    s = json.dumps(_rest.sanitize(deep))
    assert "[nested data omitted]" in s
    assert "[nested data omitted]" in json.dumps(_rest.sanitize([[[[[[[[[[1]]]]]]]]]]))
    k = list(_rest.sanitize({"K" * 999: 1}))[0]
    assert len(k) < 300


def test_missing_httpx_gives_actionable_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "httpx", None)
    try:
        with pytest.raises(ImportError, match=r"mcp-mqtt\[emqx\]"):
            importlib.reload(_rest)
    finally:
        monkeypatch.undo()
        importlib.reload(_rest)


async def call(mcp, name, args=None):
    res = await mcp.call_tool(name, args or {})
    content = res[0] if isinstance(res, tuple) else res
    return json.loads(content[0].text)


async def test_emqx_tools_async_and_paths(monkeypatch):
    paths = []

    def h(req):
        paths.append(req.url.raw_path.decode())
        return httpx.Response(200, json={"ok": 1})

    mock(monkeypatch, h)
    mcp = build_server("emqx", Settings(), emqx.extras)
    assert (await call(mcp, "emqx_stats"))["untrusted"] is True
    await call(mcp, "emqx_list_clients", {"limit": 9999})
    await call(mcp, "emqx_list_subscriptions", {"limit": -3})
    assert paths == ["/api/v5/stats", "/api/v5/clients?limit=100", "/api/v5/subscriptions?limit=1"]


async def test_nanomq_tools(monkeypatch):
    paths = []

    def h(req):
        paths.append(req.url.raw_path.decode())
        return httpx.Response(200, json=[])

    mock(monkeypatch, h)
    mcp = build_server("nanomq", Settings(), nanomq.extras)
    await call(mcp, "nanomq_stats")
    await call(mcp, "nanomq_list_clients", {"limit": 5})
    assert paths == ["/api/v4/brokers", "/api/v4/clients?_limit=5"]


async def test_rest_tools_do_not_block_event_loop(monkeypatch):
    import asyncio
    import time

    def h(req):
        time.sleep(0.3)
        return httpx.Response(200, json={})

    mock(monkeypatch, h)
    mcp = build_server("emqx", Settings(), emqx.extras)
    t0 = time.monotonic()
    await asyncio.gather(*(call(mcp, "emqx_stats") for _ in range(3)))
    assert time.monotonic() - t0 < 0.8  # concurrent, not 3 x 0.3s serial
