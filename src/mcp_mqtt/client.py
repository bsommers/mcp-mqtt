"""Thin paho-mqtt wrapper. Short-lived connections per call keep the server stateless (MCP-006)."""
from __future__ import annotations

import ssl
import threading
import time
import uuid

import paho.mqtt.client as mqtt

from .config import Settings


class BrokerError(RuntimeError):
    pass


def _new_client(s: Settings) -> mqtt.Client:
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                    client_id=f"{s.client_id_prefix}-{uuid.uuid4().hex[:8]}")
    if s.username:
        c.username_pw_set(s.username, s.password)
    if s.tls:
        c.tls_set(ca_certs=s.tls_ca, certfile=s.tls_cert, keyfile=s.tls_key,
                  cert_reqs=ssl.CERT_NONE if s.tls_insecure else ssl.CERT_REQUIRED)
        if s.tls_insecure:
            c.tls_insecure_set(True)
    return c


def _connect(s: Settings, c: mqtt.Client, timeout: float = 5.0) -> None:
    ready = threading.Event()
    result: dict = {}

    def on_connect(_c, _u, _f, rc, _p):
        result["rc"] = rc
        ready.set()

    c.on_connect = on_connect
    try:
        c.connect(s.host, s.port, keepalive=30)
    except OSError as exc:
        raise BrokerError(f"cannot reach broker: {exc.__class__.__name__}") from exc
    c.loop_start()
    if not ready.wait(timeout) or result["rc"].is_failure:
        c.loop_stop()
        raise BrokerError(f"broker connection failed: {result.get('rc', 'timeout')}")


def publish(s: Settings, topic: str, data: bytes, qos: int, retain: bool) -> dict:
    c = _new_client(s)
    _connect(s, c)
    try:
        info = c.publish(topic, data, qos=qos, retain=retain)
        info.wait_for_publish(timeout=10)
        if not info.is_published():
            raise BrokerError("publish not acknowledged within 10s")
        return {"published": True, "topic": topic, "bytes": len(data), "qos": qos, "retain": retain}
    finally:
        c.disconnect()
        c.loop_stop()


def collect(s: Settings, flt: str, qos: int, max_messages: int, wait: float) -> list[tuple[str, bytes, bool, int]]:
    """Subscribe, gather up to max_messages or until `wait` elapses, then disconnect."""
    c = _new_client(s)
    msgs: list[tuple[str, bytes, bool, int]] = []
    done = threading.Event()
    lock = threading.Lock()

    def on_message(_c, _u, m):
        with lock:
            if len(msgs) < max_messages:
                # cap per-message memory at receive time, not only at render time
                msgs.append((m.topic, bytes(m.payload[: s.max_message_bytes + 1]), bool(m.retain), m.qos))
            if len(msgs) >= max_messages:
                done.set()

    c.on_message = on_message
    _connect(s, c)
    try:
        rc, _ = c.subscribe(flt, qos=qos)
        if rc != mqtt.MQTT_ERR_SUCCESS:
            raise BrokerError("subscribe failed")
        done.wait(timeout=wait)
        time.sleep(0)  # yield
        with lock:
            return list(msgs)
    finally:
        c.disconnect()
        c.loop_stop()
