import dataclasses

import pytest

from mcp_mqtt.config import Settings

ENV = [
    "MQTT_HOST", "MQTT_PORT", "MQTT_USERNAME", "MQTT_PASSWORD", "MQTT_TLS", "MQTT_TLS_CA",
    "MQTT_TLS_CERT", "MQTT_TLS_KEY", "MQTT_TLS_INSECURE", "MQTT_PUBLISH_ALLOW",
    "MQTT_SUBSCRIBE_ALLOW", "MQTT_READ_ONLY", "MQTT_MAX_PUBLISH_BYTES", "MQTT_MAX_MESSAGE_BYTES",
    "MQTT_MAX_MESSAGES", "MQTT_MAX_RESPONSE_BYTES", "MQTT_RATE_LIMIT_PER_MINUTE",
    "MQTT_ALLOW_RETAIN", "MQTT_MAX_QOS", "MQTT_MAX_WAIT_SECONDS", "MQTT_MAX_TOPIC_LENGTH",
    "MQTT_MAX_TOPIC_LEVELS",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ENV:
        monkeypatch.delenv(k, raising=False)


def test_defaults():
    s = Settings.from_env()
    assert (s.host, s.port) == ("localhost", 1883)
    assert s.tls is False and s.tls_insecure is False and s.read_only is False
    assert s.publish_allow == () and s.subscribe_allow == ()
    assert s.allow_retain is False and s.max_qos == 1
    assert s.username is None and s.password is None
    assert s.max_publish_bytes == 65_536 and s.rate_limit_per_minute == 60


def test_tls_default_port(monkeypatch):
    monkeypatch.setenv("MQTT_TLS", "1")
    s = Settings.from_env()
    assert s.port == 8883 and s.tls is True


def test_explicit_port_overrides_tls_default(monkeypatch):
    monkeypatch.setenv("MQTT_TLS", "1")
    monkeypatch.setenv("MQTT_PORT", "9999")
    assert Settings.from_env().port == 9999


def test_tls_true_word_enables_tls(monkeypatch):
    monkeypatch.setenv("MQTT_TLS", "true")
    s = Settings.from_env()
    assert s.tls is True and s.port == 8883


def test_csv_parsing(monkeypatch):
    monkeypatch.setenv("MQTT_PUBLISH_ALLOW", " a/#, b/+ ,,c ")
    monkeypatch.setenv("MQTT_SUBSCRIBE_ALLOW", "x")
    s = Settings.from_env()
    assert s.publish_allow == ("a/#", "b/+", "c")
    assert s.subscribe_allow == ("x",)


def test_flags(monkeypatch):
    monkeypatch.setenv("MQTT_READ_ONLY", "1")
    monkeypatch.setenv("MQTT_ALLOW_RETAIN", "1")
    s = Settings.from_env()
    assert s.read_only and s.allow_retain


def test_empty_strings_become_none(monkeypatch):
    monkeypatch.setenv("MQTT_USERNAME", "")
    monkeypatch.setenv("MQTT_PASSWORD", "")
    monkeypatch.setenv("MQTT_TLS_CA", "")
    s = Settings.from_env()
    assert s.username is None and s.password is None and s.tls_ca is None


def test_tls_paths(monkeypatch):
    monkeypatch.setenv("MQTT_TLS", "1")
    monkeypatch.setenv("MQTT_TLS_CA", "/ca")
    monkeypatch.setenv("MQTT_TLS_CERT", "/c")
    monkeypatch.setenv("MQTT_TLS_KEY", "/k")
    s = Settings.from_env()
    assert (s.tls_ca, s.tls_cert, s.tls_key) == ("/ca", "/c", "/k")


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_password_plaintext_loopback_ok(monkeypatch, host):
    monkeypatch.setenv("MQTT_HOST", host)
    monkeypatch.setenv("MQTT_PASSWORD", "pw")
    assert Settings.from_env().password == "pw"


def test_password_plaintext_remote_rejected(monkeypatch):
    monkeypatch.setenv("MQTT_HOST", "broker.example.com")
    monkeypatch.setenv("MQTT_USERNAME", "u")
    monkeypatch.setenv("MQTT_PASSWORD", "pw")
    with pytest.raises(ValueError, match="plaintext"):
        Settings.from_env()


def test_password_tls_remote_ok(monkeypatch):
    monkeypatch.setenv("MQTT_HOST", "broker.example.com")
    monkeypatch.setenv("MQTT_PASSWORD", "pw")
    monkeypatch.setenv("MQTT_TLS", "1")
    assert Settings.from_env().password == "pw"


def test_no_password_remote_plain_ok(monkeypatch):
    monkeypatch.setenv("MQTT_HOST", "broker.example.com")
    assert Settings.from_env().host == "broker.example.com"


def test_insecure_without_tls_rejected(monkeypatch):
    monkeypatch.setenv("MQTT_TLS_INSECURE", "1")
    with pytest.raises(ValueError, match="INSECURE"):
        Settings.from_env()


def test_insecure_with_tls_ok(monkeypatch):
    monkeypatch.setenv("MQTT_TLS", "1")
    monkeypatch.setenv("MQTT_TLS_INSECURE", "1")
    assert Settings.from_env().tls_insecure is True


@pytest.mark.parametrize("var", [
    "MQTT_PORT", "MQTT_MAX_PUBLISH_BYTES", "MQTT_MAX_MESSAGE_BYTES", "MQTT_MAX_MESSAGES",
    "MQTT_MAX_RESPONSE_BYTES", "MQTT_RATE_LIMIT_PER_MINUTE", "MQTT_MAX_QOS",
])
@pytest.mark.parametrize("val", ["abc", "1.5", "", "1e3"])
def test_bad_ints(monkeypatch, var, val):
    monkeypatch.setenv(var, val)
    with pytest.raises(ValueError, match=var):
        Settings.from_env()


@pytest.mark.parametrize("var", [
    "MQTT_MAX_PUBLISH_BYTES", "MQTT_MAX_MESSAGE_BYTES", "MQTT_MAX_MESSAGES",
    "MQTT_MAX_RESPONSE_BYTES", "MQTT_RATE_LIMIT_PER_MINUTE",
])
@pytest.mark.parametrize("val", ["0", "-5"])
def test_limits_below_one(monkeypatch, var, val):
    monkeypatch.setenv(var, val)
    with pytest.raises(ValueError, match=">= 1"):
        Settings.from_env()


def test_limit_of_one_ok(monkeypatch):
    monkeypatch.setenv("MQTT_MAX_MESSAGES", "1")
    assert Settings.from_env().max_messages == 1


@pytest.mark.parametrize("val,exp", [("-3", 0), ("0", 0), ("1", 1), ("2", 2), ("9", 2)])
def test_max_qos_clamped(monkeypatch, val, exp):
    monkeypatch.setenv("MQTT_MAX_QOS", val)
    assert Settings.from_env().max_qos == exp


def test_password_not_in_repr():
    s = Settings(password="hunter2", username="u")
    assert "hunter2" not in repr(s)


def test_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Settings().port = 1


def test_validate_direct():
    with pytest.raises(ValueError):
        Settings(max_messages=0).validate()


SWITCHES = [("MQTT_READ_ONLY", "read_only"), ("MQTT_ALLOW_RETAIN", "allow_retain"),
            ("MQTT_TLS", "tls")]


@pytest.mark.parametrize(("var", "attr"), SWITCHES)
@pytest.mark.parametrize("val", ["1", "true", "TRUE", "Yes", "on", " on "])
def test_bool_true_values(monkeypatch, var, attr, val):
    monkeypatch.setenv(var, val)
    assert getattr(Settings.from_env(), attr) is True


@pytest.mark.parametrize(("var", "attr"), SWITCHES)
@pytest.mark.parametrize("val", ["0", "false", "No", "off", ""])
def test_bool_false_values(monkeypatch, var, attr, val):
    monkeypatch.setenv(var, val)
    assert getattr(Settings.from_env(), attr) is False


@pytest.mark.parametrize("var", ["MQTT_READ_ONLY", "MQTT_ALLOW_RETAIN", "MQTT_TLS", "MQTT_TLS_INSECURE"])
@pytest.mark.parametrize("val", ["2", "ture", "enabled", "y", "-1"])
def test_bool_garbage_rejected(monkeypatch, var, val):
    monkeypatch.setenv(var, val)
    with pytest.raises(ValueError, match=var):
        Settings.from_env()


@pytest.mark.parametrize("val", ["true", "yes", "on"])
def test_tls_insecure_word_values(monkeypatch, val):
    monkeypatch.setenv("MQTT_TLS", "1")
    monkeypatch.setenv("MQTT_TLS_INSECURE", val)
    assert Settings.from_env().tls_insecure is True


def test_tls_insecure_warns(monkeypatch, caplog):
    monkeypatch.setenv("MQTT_TLS", "1")
    monkeypatch.setenv("MQTT_TLS_INSECURE", "1")
    with caplog.at_level("WARNING", logger="mcp_mqtt"):
        Settings.from_env()
    assert "NOT verified" in caplog.text


def test_new_limit_env_vars(monkeypatch):
    monkeypatch.setenv("MQTT_MAX_WAIT_SECONDS", "12.5")
    monkeypatch.setenv("MQTT_MAX_TOPIC_LENGTH", "100")
    monkeypatch.setenv("MQTT_MAX_TOPIC_LEVELS", "4")
    s = Settings.from_env()
    assert (s.max_wait_seconds, s.max_topic_length, s.max_topic_levels) == (12.5, 100, 4)


def test_bad_wait_seconds(monkeypatch):
    monkeypatch.setenv("MQTT_MAX_WAIT_SECONDS", "abc")
    with pytest.raises(ValueError, match="number"):
        Settings.from_env()
    monkeypatch.setenv("MQTT_MAX_WAIT_SECONDS", "0")
    with pytest.raises(ValueError, match="WAIT"):
        Settings.from_env()


@pytest.mark.parametrize("port", ["0", "65536", "-5"])
def test_port_range(monkeypatch, port):
    monkeypatch.setenv("MQTT_PORT", port)
    with pytest.raises(ValueError, match="PORT"):
        Settings.from_env()


def test_message_bytes_must_fit_response(monkeypatch):
    monkeypatch.setenv("MQTT_MAX_MESSAGE_BYTES", "5000")
    monkeypatch.setenv("MQTT_MAX_RESPONSE_BYTES", "1000")
    with pytest.raises(ValueError, match="MESSAGE_BYTES"):
        Settings.from_env()


def test_topic_limits_must_be_positive():
    with pytest.raises(ValueError, match="limits"):
        Settings(max_topic_levels=0).validate()


def test_qos_clamp_warns(monkeypatch, caplog):
    monkeypatch.setenv("MQTT_MAX_QOS", "9")
    with caplog.at_level("WARNING", logger="mcp_mqtt"):
        assert Settings.from_env().max_qos == 2
    assert "clamped" in caplog.text
