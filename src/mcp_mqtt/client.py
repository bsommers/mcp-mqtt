"""Thin paho-mqtt wrapper. Short-lived connections per call keep the server stateless (MCP-006)."""
from __future__ import annotations

import ssl
import threading
import time
import uuid
from typing import Any, NamedTuple

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from .config import Settings


class BrokerError(RuntimeError):
    pass


class Received(NamedTuple):
    """An inbound message. `payload` is capped at max_message_bytes+1; `size` is the true wire size."""
    topic: str
    payload: bytes
    retained: bool
    qos: int
    size: int


# retained_only mode stops once no message has arrived for this long (the retained burst follows SUBACK)
RETAINED_QUIET_SECONDS = 0.5


def _new_client(s: Settings) -> mqtt.Client:
    c = mqtt.Client(CallbackAPIVersion.VERSION2,
                    client_id=f"{s.client_id_prefix}-{uuid.uuid4().hex[:8]}")
    try:
        if s.username:
            c.username_pw_set(s.username, s.password)
        if s.tls:
            c.tls_set(ca_certs=s.tls_ca, certfile=s.tls_cert, keyfile=s.tls_key,
                      cert_reqs=ssl.CERT_NONE if s.tls_insecure else ssl.CERT_REQUIRED)
            if s.tls_insecure:
                c.tls_insecure_set(True)
    except (OSError, ssl.SSLError, ValueError) as exc:
        # never echo exception text: it can contain local filesystem paths
        raise BrokerError("TLS configuration error (check MQTT_TLS_CA/CERT/KEY)") from exc
    return c


def _close(c: mqtt.Client) -> None:
    try:
        c.disconnect()
    except OSError:
        pass
    c.loop_stop()


def _connect(s: Settings, c: mqtt.Client, timeout: float = 5.0) -> None:
    ready = threading.Event()
    result: dict[str, Any] = {}

    def on_connect(_c: mqtt.Client, _u: Any, _f: Any, rc: Any, _p: Any) -> None:
        result["rc"] = rc
        ready.set()

    c.on_connect = on_connect
    try:
        c.connect(s.host, s.port, keepalive=30)
    except (OSError, ssl.SSLError) as exc:
        _close(c)
        raise BrokerError(f"cannot reach broker: {exc.__class__.__name__}") from exc
    c.loop_start()
    if not ready.wait(timeout) or result["rc"].is_failure:
        _close(c)
        raise BrokerError(f"broker connection failed: {result.get('rc', 'timeout')}")


def publish(s: Settings, topic: str, data: bytes, qos: int, retain: bool) -> dict[str, Any]:
    c = _new_client(s)
    _connect(s, c)
    try:
        info = c.publish(topic, data, qos=qos, retain=retain)
        info.wait_for_publish(timeout=10)
        if not info.is_published():
            raise BrokerError("publish not acknowledged within 10s")
        return {"published": True, "topic": topic, "bytes": len(data), "qos": qos, "retain": retain}
    finally:
        _close(c)


def collect(s: Settings, flt: str, qos: int, max_messages: int, wait: float,
            retained_only: bool = False) -> list[Received]:
    """Subscribe, gather up to max_messages or until `wait` elapses, then disconnect.

    With retained_only, non-retained (live) messages are never collected: the call ends at the
    first live message, or once the retained burst has gone quiet.
    """
    c = _new_client(s)
    msgs: list[Received] = []
    done = threading.Event()
    lock = threading.Lock()
    last = [time.monotonic()]

    def on_message(_c: mqtt.Client, _u: Any, m: mqtt.MQTTMessage) -> None:
        with lock:
            if done.is_set():
                return
            last[0] = time.monotonic()
            if retained_only and not m.retain:
                done.set()
                return
            if len(msgs) < max_messages:
                # cap per-message memory at receive time, but remember the true size
                msgs.append(Received(m.topic, bytes(m.payload[: s.max_message_bytes + 1]),
                                     bool(m.retain), m.qos, len(m.payload)))
            if len(msgs) >= max_messages:
                done.set()

    c.on_message = on_message
    _connect(s, c)
    try:
        rc, _ = c.subscribe(flt, qos=qos)
        if rc != mqtt.MQTT_ERR_SUCCESS:
            raise BrokerError("subscribe failed")
        with lock:
            last[0] = time.monotonic()
        deadline = time.monotonic() + wait
        while not done.is_set():
            now = time.monotonic()
            if now >= deadline:
                break
            if retained_only:
                with lock:
                    idle = now - last[0]
                if idle >= RETAINED_QUIET_SECONDS:
                    break
            done.wait(timeout=min(0.05, deadline - now))
        with lock:
            return list(msgs)
    finally:
        _close(c)
