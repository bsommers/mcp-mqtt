"""Pure, broker-independent guards: topic validation, allowlists, payload bounds, rate limiting."""
from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass
from typing import Any

from .config import Settings


class GuardError(ValueError):
    """Raised when a request violates a security policy. Message is safe to show the LLM."""


def _check_common(topic: str, s: Settings) -> list[str]:
    if not isinstance(topic, str) or not topic:
        raise GuardError("topic must be a non-empty string")
    if "\x00" in topic or any(ord(c) < 0x20 or ord(c) == 0x7F for c in topic):
        raise GuardError("topic contains control characters")
    if len(topic.encode("utf-8")) > s.max_topic_length:
        raise GuardError(f"topic exceeds {s.max_topic_length} bytes")
    levels = topic.split("/")
    if len(levels) > s.max_topic_levels:
        raise GuardError(f"topic exceeds {s.max_topic_levels} levels")
    return levels


def validate_publish_topic(topic: str, s: Settings) -> str:
    """Publish topics: no wildcards, no $-reserved topics (e.g. $SYS), must match allowlist."""
    _check_common(topic, s)
    if "+" in topic or "#" in topic:
        raise GuardError("wildcards are not allowed in publish topics")
    if topic.startswith("$"):
        raise GuardError("publishing to $-prefixed (broker reserved) topics is not allowed")
    # empty topic levels are legal MQTT; the allowlist still applies
    if not any(topic_matches(p, topic) for p in s.publish_allow):
        raise GuardError("topic not permitted by MQTT_PUBLISH_ALLOW")
    return topic


def validate_subscribe_filter(flt: str, s: Settings) -> str:
    """Subscribe filters must be fully covered by an allowlist entry (no wildcard escalation)."""
    levels = _check_common(flt, s)
    for i, lv in enumerate(levels):
        if "#" in lv and (lv != "#" or i != len(levels) - 1):
            raise GuardError("invalid '#' wildcard placement")
        if "+" in lv and lv != "+":
            raise GuardError("invalid '+' wildcard placement")
    if not any(filter_covered_by(flt, p) for p in s.subscribe_allow):
        raise GuardError("subscription not permitted by MQTT_SUBSCRIBE_ALLOW")
    return flt


def topic_matches(pattern: str, topic: str) -> bool:
    """MQTT filter match of concrete topic against pattern (supports + and #)."""
    p, t = pattern.split("/"), topic.split("/")
    for i, seg in enumerate(p):
        if seg == "#":
            return i == len(p) - 1
        if i >= len(t):
            return False
        if seg != "+" and seg != t[i]:
            return False
    return len(p) == len(t)


def filter_covered_by(flt: str, allow: str) -> bool:
    """True if every topic matched by `flt` is also matched by `allow`."""
    f, a = flt.split("/"), allow.split("/")
    # MQTT: a leading wildcard never matches $-topics; $SYS etc. need an explicit $ allow entry.
    if f[0].startswith("$") and not a[0].startswith("$"):
        return False
    for i, aseg in enumerate(a):
        if aseg == "#":
            return i == len(a) - 1
        if i >= len(f):
            return False
        fseg = f[i]
        if fseg == "#":
            return False  # f is broader than a (a has no # here)
        if aseg == "+":
            continue
        if fseg == "+" or fseg != aseg:
            return False
    return len(f) == len(a)


def validate_qos(qos: int, s: Settings) -> int:
    if not isinstance(qos, int) or isinstance(qos, bool) or not 0 <= qos <= s.max_qos:
        raise GuardError(f"qos must be an integer 0..{s.max_qos}")
    return qos


def encode_publish_payload(payload: str, encoding: str, s: Settings) -> bytes:
    """Decode the LLM-supplied payload and enforce the byte cap on the *decoded* size."""
    if encoding == "base64":
        # cheap pre-check before decoding to avoid allocating huge buffers
        if len(payload) > (s.max_publish_bytes * 4) // 3 + 4:
            raise GuardError(f"payload exceeds {s.max_publish_bytes} bytes")
        try:
            data = base64.b64decode(payload, validate=True)
        except Exception as exc:
            raise GuardError("payload is not valid base64") from exc
    elif encoding == "utf8":
        if len(payload) > s.max_publish_bytes:  # chars <= bytes, so this is a safe pre-check
            raise GuardError(f"payload exceeds {s.max_publish_bytes} bytes")
        data = payload.encode("utf-8")
    else:
        raise GuardError("encoding must be 'utf8' or 'base64'")
    if len(data) > s.max_publish_bytes:
        raise GuardError(f"payload exceeds {s.max_publish_bytes} bytes")
    return data


@dataclass
class RateLimiter:
    """Token bucket, thread-safe. One shared instance per server process."""
    per_minute: int
    _tokens: float = 0.0
    _last: float = 0.0
    _lock: threading.Lock = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._tokens = float(self.per_minute)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def check(self) -> None:
        with self._lock:
            now = time.monotonic()
            self._tokens = min(self.per_minute, self._tokens + (now - self._last) * self.per_minute / 60)
            self._last = now
            if self._tokens < 1:
                raise GuardError("rate limit exceeded; retry later")
            self._tokens -= 1


def _utf8_prefix(chunk: bytes) -> str:
    """Decode a possibly truncated chunk, dropping a trailing partial UTF-8 sequence (max 3 bytes)."""
    try:
        return chunk.decode("utf-8")
    except UnicodeDecodeError as exc:
        # only a partial sequence at the very end is forgivable; anything earlier is binary
        if exc.end == len(chunk) and len(chunk) - exc.start <= 3 and exc.reason == "unexpected end of data":
            return chunk[: exc.start].decode("utf-8")
        raise


def render_inbound(topic: str, payload: bytes, s: Settings, retained: bool = False, qos: int = 0,
                   size: int | None = None) -> dict[str, Any]:
    """Shape an inbound broker message for the LLM.

    Payloads are UNTRUSTED data (possible prompt injection): they are bounded, never
    interpreted, and always returned in a structured field flagged as untrusted.
    """
    total = max(len(payload), size or 0)  # `size` is the true wire size when payload was pre-capped
    truncated = total > s.max_message_bytes
    chunk = payload[: s.max_message_bytes]
    try:
        text, enc = (_utf8_prefix(chunk) if truncated else chunk.decode("utf-8")), "utf8"
        if any(ord(c) < 0x20 and c not in "\n\r\t" for c in text):
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "control")
    except UnicodeDecodeError:
        text, enc = base64.b64encode(chunk).decode("ascii"), "base64"
    return {
        "topic": topic[: s.max_topic_length],
        "payload": text,
        "encoding": enc,
        "bytes": total,
        "truncated": truncated,
        "retained": retained,
        "qos": qos,
        "untrusted": True,
    }


def bound_messages(msgs: list[dict[str, Any]], s: Settings) -> tuple[list[dict[str, Any]], bool]:
    """Dual-axis bounding (MCP-003): cardinality first, then total byte budget."""
    out: list[dict[str, Any]] = []
    size, cut = 0, False
    for m in msgs[: s.max_messages]:
        sz = len(json.dumps(m))
        if size + sz > s.max_response_bytes:
            cut = True
            break
        out.append(m)
        size += sz
    return out, cut or len(msgs) > s.max_messages
