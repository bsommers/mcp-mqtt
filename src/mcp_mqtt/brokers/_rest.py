"""Shared read-only REST helper for broker management APIs (EMQX, NanoMQ).

Credentials come only from server env, never tool params. Responses are broker data that any MQTT
client can influence (client IDs, usernames, topics), so they are bounded and flagged untrusted.
Requires the optional `httpx` dependency: pip install 'mcp-mqtt[emqx]' (or '[nanomq]').
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

try:
    import httpx
except ImportError as exc:  # pragma: no cover - exercised via a reload test
    raise ImportError(
        "httpx is required for the EMQX/NanoMQ profiles: pip install 'mcp-mqtt[emqx]' or 'mcp-mqtt[nanomq]'"
    ) from exc

from ..config import Settings
from ..security import GuardError, RateLimiter

log = logging.getLogger("mcp_mqtt")

TIMEOUT = 5.0
MAX_LIMIT = 100
MAX_FIELD_CHARS = 256   # per string value returned to the model
MAX_LIST_ITEMS = 200
MAX_DEPTH = 8
LOOPBACK = ("localhost", "127.0.0.1", "::1")

# Test seam: tests inject an httpx.MockTransport here.
_transport: httpx.BaseTransport | None = None


@dataclass(frozen=True)
class RestProfile:
    name: str
    url_env: str
    default_url: str
    user_env: str
    secret_env: str

    @property
    def missing_msg(self) -> str:
        if self.user_env == self.secret_env:
            return f"{self.user_env} not configured"
        return f"{self.user_env}/{self.secret_env} not configured"


def base_url(profile: RestProfile, has_credentials: bool = True) -> str:
    url = os.environ.get(profile.url_env, profile.default_url).rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise GuardError(f"{profile.url_env} must be an http(s) URL")
    if parts.scheme == "http" and has_credentials and parts.hostname not in LOOPBACK:
        raise GuardError(
            f"refusing to send credentials over plaintext http to a non-loopback host; "
            f"use https in {profile.url_env}"
        )
    return url


def sanitize(value: Any, depth: int = 0) -> Any:
    """Bound untrusted structure: cap string length, list size and nesting depth."""
    if isinstance(value, str):
        return value if len(value) <= MAX_FIELD_CHARS else value[:MAX_FIELD_CHARS] + "...[truncated]"
    if isinstance(value, dict):
        if depth >= MAX_DEPTH:
            return "[nested data omitted]"
        return {sanitize(str(k), depth + 1): sanitize(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        if depth >= MAX_DEPTH:
            return "[nested data omitted]"
        return [sanitize(v, depth + 1) for v in value[:MAX_LIST_ITEMS]]
    return value


def rest_get(settings: Settings, limiter: RateLimiter, profile: RestProfile, path: str) -> str:
    """Blocking GET; call via asyncio.to_thread. Always returns a JSON string."""
    user = os.environ.get(profile.user_env)
    secret = os.environ.get(profile.secret_env)
    if not user or not secret:
        return json.dumps({"ok": False, "error": profile.missing_msg})
    try:
        limiter.check()
        url = base_url(profile) + path
        buf = bytearray()
        cap = settings.max_response_bytes
        with httpx.Client(timeout=TIMEOUT, follow_redirects=False, auth=(user, secret),
                          transport=_transport) as c, c.stream("GET", url) as r:
            if r.status_code != 200:
                return json.dumps({"ok": False, "error": f"HTTP {r.status_code}"})
            for chunk in r.iter_bytes():
                buf += chunk
                if len(buf) > cap:
                    break
        truncated = len(buf) > cap
        text = bytes(buf[:cap]).decode("utf-8", "replace")
        if truncated:
            return json.dumps({"ok": True, "untrusted": True, "truncated": True,
                               "data": sanitize(text)})
        try:
            data: Any = sanitize(json.loads(text))
        except ValueError:
            data = sanitize(text)
        return json.dumps({"ok": True, "untrusted": True, "truncated": False, "data": data})
    except GuardError as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    except httpx.HTTPError as exc:
        log.warning("%s api error: %s", profile.name, type(exc).__name__)
        return json.dumps({"ok": False, "error": f"API request failed: {type(exc).__name__}"})
