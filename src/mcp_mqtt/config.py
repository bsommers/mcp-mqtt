"""Settings loaded ONLY from server-side environment (MCP-001): never from tool inputs."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

log = logging.getLogger("mcp_mqtt")


def _csv(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(p.strip() for p in os.environ.get(name, default).split(",") if p.strip())


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})


def _bool(name: str, default: bool = False) -> bool:
    """Strict boolean switch: unrecognised values raise instead of silently failing open."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    raise ValueError(f"{name} must be one of 1/true/yes/on or 0/false/no/off")


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


@dataclass(frozen=True)
class Settings:
    host: str = "localhost"
    port: int = 1883
    username: str | None = None
    password: str | None = field(default=None, repr=False)
    tls: bool = False
    tls_ca: str | None = None
    tls_cert: str | None = None
    tls_key: str | None = None
    tls_insecure: bool = False
    client_id_prefix: str = "mcp-mqtt"
    # Authorization: deny-by-default. Empty allowlist == nothing permitted.
    publish_allow: tuple[str, ...] = ()
    subscribe_allow: tuple[str, ...] = ()
    read_only: bool = False
    # Resource bounds (MCP-003 / MCP-006)
    max_publish_bytes: int = 65_536
    max_message_bytes: int = 8_192       # per inbound message returned to the LLM
    max_messages: int = 100              # per subscribe call
    max_response_bytes: int = 32_768     # total tool response budget
    max_wait_seconds: float = 30.0
    max_topic_length: int = 256
    max_topic_levels: int = 16
    rate_limit_per_minute: int = 60
    allow_retain: bool = False
    max_qos: int = 1

    @classmethod
    def from_env(cls) -> Settings:
        tls = _bool("MQTT_TLS")
        qos_raw = _int("MQTT_MAX_QOS", 1)
        s = cls(
            host=os.environ.get("MQTT_HOST", "localhost"),
            port=_int("MQTT_PORT", 8883 if tls else 1883),
            username=os.environ.get("MQTT_USERNAME") or None,
            password=os.environ.get("MQTT_PASSWORD") or None,
            tls=tls,
            tls_ca=os.environ.get("MQTT_TLS_CA") or None,
            tls_cert=os.environ.get("MQTT_TLS_CERT") or None,
            tls_key=os.environ.get("MQTT_TLS_KEY") or None,
            tls_insecure=_bool("MQTT_TLS_INSECURE"),
            publish_allow=_csv("MQTT_PUBLISH_ALLOW"),
            subscribe_allow=_csv("MQTT_SUBSCRIBE_ALLOW"),
            read_only=_bool("MQTT_READ_ONLY"),
            max_publish_bytes=_int("MQTT_MAX_PUBLISH_BYTES", 65_536),
            max_message_bytes=_int("MQTT_MAX_MESSAGE_BYTES", 8_192),
            max_messages=_int("MQTT_MAX_MESSAGES", 100),
            max_response_bytes=_int("MQTT_MAX_RESPONSE_BYTES", 32_768),
            max_wait_seconds=_float("MQTT_MAX_WAIT_SECONDS", 30.0),
            max_topic_length=_int("MQTT_MAX_TOPIC_LENGTH", 256),
            max_topic_levels=_int("MQTT_MAX_TOPIC_LEVELS", 16),
            rate_limit_per_minute=_int("MQTT_RATE_LIMIT_PER_MINUTE", 60),
            allow_retain=_bool("MQTT_ALLOW_RETAIN"),
            max_qos=min(2, max(0, qos_raw)),
        )
        if qos_raw != s.max_qos:
            log.warning("MQTT_MAX_QOS=%d out of range, clamped to %d", qos_raw, s.max_qos)
        s.validate()
        if s.tls_insecure:
            log.warning("MQTT_TLS_INSECURE is set: broker certificates are NOT verified")
        return s

    def validate(self) -> None:
        if self.tls_insecure and not self.tls:
            raise ValueError("MQTT_TLS_INSECURE requires MQTT_TLS=1")
        for v in (self.max_publish_bytes, self.max_message_bytes, self.max_messages,
                  self.max_response_bytes, self.rate_limit_per_minute,
                  self.max_topic_length, self.max_topic_levels):
            if v < 1:
                raise ValueError("limits must be >= 1")
        if not 1 <= self.port <= 65535:
            raise ValueError("MQTT_PORT must be 1..65535")
        if self.max_message_bytes > self.max_response_bytes:
            raise ValueError("MQTT_MAX_MESSAGE_BYTES must be <= MQTT_MAX_RESPONSE_BYTES")
        if not 0 < self.max_wait_seconds <= 3600:
            raise ValueError("MQTT_MAX_WAIT_SECONDS must be > 0 and <= 3600")
        if self.password and not self.tls and self.host not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("refusing to send credentials over plaintext to a non-loopback host; set MQTT_TLS=1")
