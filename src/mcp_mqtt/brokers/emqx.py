"""EMQX 5.x profile. Read-only REST helpers; credentials come only from server env, never tool params."""
from __future__ import annotations

import json
import logging
import os
from urllib.parse import urlsplit

import httpx

from ..security import GuardError
from ..server import run

log = logging.getLogger("mcp_mqtt")

_TIMEOUT = 5.0
_MAX_LIMIT = 100


def _base_url() -> str:
    url = os.environ.get("EMQX_API_URL", "http://localhost:18083").rstrip("/")
    if urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).hostname:
        raise GuardError("EMQX_API_URL must be an http(s) URL")
    return url


def _get(settings, limiter, path: str) -> str:
    user = os.environ.get("EMQX_API_KEY")
    secret = os.environ.get("EMQX_API_SECRET")
    if not user or not secret:
        return json.dumps({"ok": False, "error": "EMQX_API_KEY not configured"})
    try:
        limiter.check()
        url = _base_url() + path
        buf = bytearray()
        cap = settings.max_response_bytes
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=False, auth=(user, secret)) as c:
            with c.stream("GET", url) as r:
                if r.status_code != 200:
                    return json.dumps({"ok": False, "error": f"HTTP {r.status_code}"})
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > cap:
                        break
        truncated = len(buf) > cap
        text = bytes(buf[:cap]).decode("utf-8", "replace")
        if truncated:
            return json.dumps({"ok": True, "truncated": True, "data": text})
        try:
            return json.dumps({"ok": True, "truncated": False, "data": json.loads(text)})
        except ValueError:
            return json.dumps({"ok": True, "truncated": False, "data": text})
    except GuardError as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    except httpx.HTTPError as exc:
        log.warning("emqx api error: %s", type(exc).__name__)
        return json.dumps({"ok": False, "error": f"API request failed: {type(exc).__name__}"})


def extras(mcp, settings, limiter):
    @mcp.tool()
    def emqx_stats() -> str:
        """Get EMQX broker statistics."""
        return _get(settings, limiter, "/api/v5/stats")

    @mcp.tool()
    def emqx_list_clients(limit: int = 20) -> str:
        """List connected EMQX clients. limit is capped at 100."""
        n = max(1, min(int(limit), _MAX_LIMIT))
        return _get(settings, limiter, f"/api/v5/clients?limit={n}")

    @mcp.tool()
    def emqx_list_subscriptions(limit: int = 20) -> str:
        """List EMQX subscriptions. limit is capped at 100."""
        n = max(1, min(int(limit), _MAX_LIMIT))
        return _get(settings, limiter, f"/api/v5/subscriptions?limit={n}")


def main() -> None:
    run("emqx-mqtt", extras)


if __name__ == "__main__":
    main()

