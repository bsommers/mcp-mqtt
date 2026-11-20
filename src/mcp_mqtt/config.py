"""Settings loaded ONLY from server-side environment (MCP-001): never from tool inputs."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _csv(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(p.strip() for p in os.environ.get(name, default).split(",") if p.strip())


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


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
        s = cls(
            host=os.environ.get("MQTT_HOST", "localhost"),
            port=_int("MQTT_PORT", 8883 if os.environ.get("MQTT_TLS") == "1" else 1883),
            username=os.environ.get("MQTT_USERNAME") or None,
            password=os.environ.get("MQTT_PASSWORD") or None,
            tls=os.environ.get("MQTT_TLS") == "1",
            tls_ca=os.environ.get("MQTT_TLS_CA") or None,
            tls_cert=os.environ.get("MQTT_TLS_CERT") or None,
            tls_key=os.environ.get("MQTT_TLS_KEY") or None,
            tls_insecure=os.environ.get("MQTT_TLS_INSECURE") == "1",
            publish_allow=_csv("MQTT_PUBLISH_ALLOW"),
            subscribe_allow=_csv("MQTT_SUBSCRIBE_ALLOW"),
            read_only=os.environ.get("MQTT_READ_ONLY") == "1",
            max_publish_bytes=_int("MQTT_MAX_PUBLISH_BYTES", 65_536),
            max_message_bytes=_int("MQTT_MAX_MESSAGE_BYTES", 8_192),
            max_messages=_int("MQTT_MAX_MESSAGES", 100),
            max_response_bytes=_int("MQTT_MAX_RESPONSE_BYTES", 32_768),
            rate_limit_per_minute=_int("MQTT_RATE_LIMIT_PER_MINUTE", 60),
            allow_retain=os.environ.get("MQTT_ALLOW_RETAIN") == "1",
            max_qos=min(2, max(0, _int("MQTT_MAX_QOS", 1))),
        )
        s.validate()
        return s

    def validate(self) -> None:
        if self.tls_insecure and not self.tls:
            raise ValueError("MQTT_TLS_INSECURE requires MQTT_TLS=1")
        if self.password and not self.tls and self.host not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("refusing to send credentials over plaintext to a non-loopback host; set MQTT_TLS=1")
        for v in (self.max_publish_bytes, self.max_message_bytes, self.max_messages,
                  self.max_response_bytes, self.rate_limit_per_minute):
            if v < 1:
                raise ValueError("limits must be >= 1")
