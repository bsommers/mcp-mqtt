"""client.py against a fake paho Client (no broker needed)."""
import ssl
import types

import pytest

from mcp_mqtt import client
from mcp_mqtt.config import Settings


class RC:
    def __init__(self, failure=False):
        self.is_failure = failure

    def __str__(self):
        return "Not authorized" if self.is_failure else "Success"


class Info:
    def __init__(self, ok=True):
        self.ok = ok

    def wait_for_publish(self, timeout=None):
        pass

    def is_published(self):
        return self.ok


class Fake:
    """Scriptable stand-in for paho's Client. Class attributes are reset per test by the fixture."""
    instances: list = []
    connect_exc: Exception | None = None
    tls_exc: Exception | None = None
    rc = RC()
    fire_connect = True
    sub_rc = 0
    inbound: list = []
    publish_ok = True

    def __init__(self, *a, **kw):
        self.kw = kw
        self.calls = []
        self.on_connect = None
        self.on_message = None
        Fake.instances.append(self)

    def username_pw_set(self, u, p):
        self.calls.append(("auth", u, p))

    def tls_set(self, **kw):
        if Fake.tls_exc:
            raise Fake.tls_exc
        self.calls.append(("tls", kw))

    def tls_insecure_set(self, v):
        self.calls.append(("insecure", v))

    def connect(self, host, port, keepalive=60):
        if Fake.connect_exc:
            raise Fake.connect_exc
        self.calls.append(("connect", host, port))

    def loop_start(self):
        if Fake.fire_connect and self.on_connect:
            self.on_connect(self, None, None, Fake.rc, None)

    def loop_stop(self):
        self.calls.append(("loop_stop",))

    def disconnect(self):
        self.calls.append(("disconnect",))

    def subscribe(self, flt, qos=0):
        self.calls.append(("subscribe", flt, qos))
        if Fake.sub_rc == 0:
            for m in Fake.inbound:
                self.on_message(self, None, m)
        return Fake.sub_rc, 1

    def publish(self, topic, data, qos=0, retain=False):
        self.calls.append(("publish", topic, data, qos, retain))
        return Info(Fake.publish_ok)


def msg(topic="t", payload=b"x", retain=False, qos=0):
    return types.SimpleNamespace(topic=topic, payload=payload, retain=retain, qos=qos)


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    Fake.instances = []
    Fake.connect_exc = Fake.tls_exc = None
    Fake.rc = RC()
    Fake.fire_connect = True
    Fake.sub_rc = 0
    Fake.inbound = []
    Fake.publish_ok = True
    monkeypatch.setattr(client.mqtt, "Client", Fake)
    monkeypatch.setattr(client, "RETAINED_QUIET_SECONDS", 0.05)
    return Fake


def S(**kw):
    return Settings(**kw)


def names(c):
    return [x[0] for x in c.calls]


def test_publish_ok_and_cleanup():
    r = client.publish(S(), "a/b", b"hi", 1, True)
    assert r == {"published": True, "topic": "a/b", "bytes": 2, "qos": 1, "retain": True}
    c = Fake.instances[0]
    assert ("publish", "a/b", b"hi", 1, True) in c.calls
    assert names(c)[-2:] == ["disconnect", "loop_stop"]


def test_publish_unacknowledged(fake):
    fake.publish_ok = False
    with pytest.raises(client.BrokerError, match="not acknowledged"):
        client.publish(S(), "a", b"x", 0, False)
    assert "disconnect" in names(fake.instances[0])


def test_auth_and_tls_configured():
    s = S(username="u", password="p", tls=True, tls_ca="/ca", tls_cert="/c", tls_key="/k")
    client.publish(s, "a", b"x", 0, False)
    c = Fake.instances[0]
    assert ("auth", "u", "p") in c.calls
    tls = next(x for x in c.calls if x[0] == "tls")[1]
    assert tls == {"ca_certs": "/ca", "certfile": "/c", "keyfile": "/k", "cert_reqs": ssl.CERT_REQUIRED}
    assert "insecure" not in names(c)


def test_tls_insecure_sets_flags():
    client.publish(S(tls=True, tls_insecure=True), "a", b"x", 0, False)
    c = Fake.instances[0]
    assert ("insecure", True) in c.calls
    assert next(x for x in c.calls if x[0] == "tls")[1]["cert_reqs"] == ssl.CERT_NONE


@pytest.mark.parametrize("exc", [FileNotFoundError("/secret/path/ca.pem"), ssl.SSLError("bad /secret/key")])
def test_tls_config_error_wrapped_without_path(fake, exc):
    fake.tls_exc = exc
    with pytest.raises(client.BrokerError) as ei:
        client.publish(S(tls=True, tls_ca="/secret/path/ca.pem"), "a", b"x", 0, False)
    assert "/secret" not in str(ei.value)


def test_connect_oserror_wrapped_and_closed(fake):
    fake.connect_exc = ConnectionRefusedError("nope 10.0.0.1")
    with pytest.raises(client.BrokerError, match="ConnectionRefusedError") as ei:
        client.publish(S(), "a", b"x", 0, False)
    assert "10.0.0.1" not in str(ei.value)
    assert "disconnect" in names(fake.instances[0])


def test_connect_timeout_disconnects(fake, monkeypatch):
    fake.fire_connect = False
    orig = client._connect
    monkeypatch.setattr(client, "_connect", lambda s, c, timeout=5.0: orig(s, c, timeout=0.05))
    with pytest.raises(client.BrokerError, match="timeout"):
        client.publish(S(), "a", b"x", 0, False)
    assert names(fake.instances[0])[-2:] == ["disconnect", "loop_stop"]


def test_connect_refused_rc(fake):
    fake.rc = RC(failure=True)
    with pytest.raises(client.BrokerError, match="connection failed"):
        client.publish(S(), "a", b"x", 0, False)
    assert "disconnect" in names(fake.instances[0])


def test_close_tolerates_disconnect_oserror(fake):
    c = Fake()
    c.disconnect = lambda: (_ for _ in ()).throw(OSError("closed"))
    client._close(c)
    assert "loop_stop" in names(c)


def test_collect_caps_count_and_true_size():
    Fake.inbound = [msg("a", b"x" * 100), msg("b", b"y"), msg("c", b"z")]
    out = client.collect(S(max_message_bytes=10), "#", 0, 2, 1.0)
    assert [m.topic for m in out] == ["a", "b"]
    assert len(out[0].payload) == 11 and out[0].size == 100  # capped at max+1, size is true
    assert out[1].size == 1


def test_collect_waits_then_returns_empty():
    assert client.collect(S(), "a", 0, 5, 0.1) == []


def test_collect_subscribe_failure_cleans_up(fake):
    fake.sub_rc = 4
    with pytest.raises(client.BrokerError, match="subscribe failed"):
        client.collect(S(), "a", 0, 5, 0.1)
    assert names(fake.instances[0])[-2:] == ["disconnect", "loop_stop"]


def test_collect_retained_only_skips_live_and_stops():
    Fake.inbound = [msg("r1", b"1", True), msg("live", b"2", False), msg("r2", b"3", True)]
    out = client.collect(S(), "#", 0, 10, 5.0, retained_only=True)
    assert [m.topic for m in out] == ["r1"]  # stops at first live message


def test_collect_retained_only_quiet_period_ends_early():
    import time
    Fake.inbound = [msg("r1", b"1", True), msg("r2", b"2", True)]
    t0 = time.monotonic()
    out = client.collect(S(), "#", 0, 10, 5.0, retained_only=True)
    assert [m.topic for m in out] == ["r1", "r2"]
    assert time.monotonic() - t0 < 2.0


def test_collect_default_keeps_live_messages():
    Fake.inbound = [msg("live", b"2", False)]
    assert len(client.collect(S(), "#", 0, 10, 0.1)) == 1
