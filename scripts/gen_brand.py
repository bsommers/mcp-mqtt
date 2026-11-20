#!/usr/bin/env python3
"""Deterministic TRON-inspired brand kit generator for mcp-mqtt (stdlib only).

Writes SVGs under docs/assets, docs/assets/icons, docs/diagrams and assets/,
then rasterizes PNGs with the first available renderer
(rsvg-convert, inkscape, magick).

    python3 scripts/gen_brand.py
"""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
BG, CY, SKY, DEEP, OR = "#050811", "#00e5ff", "#38bdf8", "#0284c7", "#ff8a00"
PANEL, WHITE, MUTED = "#0b1428", "#f0f6fc", "#94a3b8"
MONO = "ui-monospace, 'Cascadia Code', 'Fira Code', Menlo, Consolas, monospace"
SANS = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
NS = 'xmlns="http://www.w3.org/2000/svg"'

# ---------------------------------------------------------------- primitives


def defs(extra: str = "") -> str:
    return f"""<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#04070f"/><stop offset="0.5" stop-color="#081022"/><stop offset="1" stop-color="#040814"/></linearGradient>
<radialGradient id="halo" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{CY}" stop-opacity="0.22"/><stop offset="1" stop-color="{BG}" stop-opacity="0"/></radialGradient>
<pattern id="g1" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="{SKY}" stroke-width="0.5" stroke-opacity="0.10"/></pattern>
<pattern id="g2" width="96" height="96" patternUnits="userSpaceOnUse"><rect width="96" height="96" fill="url(#g1)"/><path d="M96 0H0V96" fill="none" stroke="{CY}" stroke-width="0.9" stroke-opacity="0.18"/><circle r="1.6" fill="{CY}" fill-opacity="0.35"/></pattern>
<filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="glowS" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="1.6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<marker id="ac" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1L9 5L1 9z" fill="{CY}"/></marker>
<marker id="ao" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1L9 5L1 9z" fill="{OR}"/></marker>
{extra}</defs>"""


def svg(w: int, h: int, body: str, title: str, desc: str, extra_defs: str = "", fixed: bool = True) -> str:
    size = f' width="{w}" height="{h}"' if fixed else ""
    return (f'<svg {NS} viewBox="0 0 {w} {h}"{size} role="img" aria-labelledby="t d">\n'
            f'<title id="t">{escape(title)}</title><desc id="d">{escape(desc)}</desc>\n'
            f'{defs(extra_defs)}\n{body}\n</svg>\n')


def canvas(w: int, h: int, rx: int = 0) -> str:
    return (f'<rect width="{w}" height="{h}" rx="{rx}" fill="url(#bg)"/>'
            f'<rect width="{w}" height="{h}" rx="{rx}" fill="url(#g2)"/>')


def reticles(x, y, w, h, s=12, c=CY, sw=2) -> str:
    return (f'<path d="M{x} {y+s}V{y}H{x+s}M{x+w-s} {y}H{x+w}V{y+s}M{x} {y+h-s}V{y+h}H{x+s}'
            f'M{x+w-s} {y+h}H{x+w}V{y+h-s}" fill="none" stroke="{c}" stroke-width="{sw}"/>')


def hexpts(cx, cy, r, rot=-90) -> str:
    return " ".join(f"{cx + r*math.cos(math.radians(rot+60*i)):.1f},{cy + r*math.sin(math.radians(rot+60*i)):.1f}"
                    for i in range(6))


def text(x, y, s, size=14, fill=WHITE, anchor="start", family=MONO, weight="400", ls=0, extra="") -> str:
    sp = f' letter-spacing="{ls}"' if ls else ""
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{sp}{extra}>{escape(s)}</text>')


# ---------------------------------------------------------------- emblem


def emblem(cx: float, cy: float, k: float = 1.0) -> str:
    """Identity disc + hexagonal broker hub + publish (in, orange) / subscribe (out) arrows.

    Designed on a 512 grid (centre 256,256); strokes >= 12 units.  k scales it.
    """
    t = f'translate({cx - 256*k:.2f} {cy - 256*k:.2f}) scale({k})'
    ring = []
    r = 218
    for a0 in (14, 104, 194, 284):
        a1 = a0 + 62
        p0 = (256 + r*math.cos(math.radians(a0)), 256 + r*math.sin(math.radians(a0)))
        p1 = (256 + r*math.cos(math.radians(a1)), 256 + r*math.sin(math.radians(a1)))
        ring.append(f"M{p0[0]:.1f} {p0[1]:.1f}A{r} {r} 0 0 1 {p1[0]:.1f} {p1[1]:.1f}")
    return f"""<g transform="{t}">
<circle cx="256" cy="256" r="236" fill="url(#halo)"/>
<path d="{' '.join(ring)}" fill="none" stroke="{SKY}" stroke-width="14" stroke-linecap="round" filter="url(#glow)"/>
<polygon points="{hexpts(256, 256, 128)}" fill="{PANEL}" fill-opacity="0.92" stroke="{CY}" stroke-width="16" stroke-linejoin="round" filter="url(#glow)"/>
<circle cx="256" cy="256" r="42" fill="{CY}" filter="url(#glow)"/>
<circle cx="256" cy="256" r="16" fill="{BG}"/>
<path d="M14 256H146M96 222L146 256L96 290" fill="none" stroke="{OR}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/>
<path d="M368 256H498M452 222L498 256L452 290" fill="none" stroke="{CY}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/>
</g>"""


# ---------------------------------------------------------------- logo / icon / favicon


def logo_svg() -> str:
    w, h = 1200, 360
    body = canvas(w, h)
    floor = "".join(f'<path d="M{600+(i-8)*30} 250L{600+(i-8)*150} 360" stroke="{CY}" stroke-opacity="0.13" stroke-width="1"/>'
                    for i in range(17))
    floor += "".join(f'<path d="M0 {y}H1200" stroke="{CY}" stroke-opacity="0.11" stroke-width="1"/>' for y in (262, 282, 312, 350))
    body += floor
    body += f'<rect x="12" y="12" width="{w-24}" height="{h-24}" fill="none" stroke="{CY}" stroke-opacity="0.35" stroke-width="1.5"/>'
    body += reticles(12, 12, w - 24, h - 24, 22)
    body += emblem(190, 180, 0.62)
    body += f'<path d="M360 118H1130" stroke="{CY}" stroke-opacity="0.35" stroke-width="2"/>'
    body += f'<path d="M1050 118H1130" stroke="{OR}" stroke-width="4" stroke-linecap="round" filter="url(#glowS)"/>'
    body += text(366, 100, "// MODEL CONTEXT PROTOCOL  x  MQTT", 15, SKY, ls=3)
    body += text(362, 192, "mcp-mqtt", 92, WHITE, weight="700", ls=2, extra=' filter="url(#glowS)"')
    body += text(366, 232, "Guarded MCP servers for Mosquitto, EMQX and NanoMQ", 20, MUTED, family=SANS)
    for label, x in (("MOSQUITTO", 366), ("EMQX", 536), ("NANOMQ", 646)):
        cw = len(label) * 11 + 28
        body += (f'<rect x="{x}" y="256" width="{cw}" height="30" fill="{PANEL}" stroke="{SKY}" stroke-width="1.5"/>'
                 + text(x + cw / 2, 276, label, 14, CY, "middle", weight="700", ls=1.5))
    body += text(1130, 300, "deny-by-default  |  bounded  |  untrusted-aware", 13, MUTED, "end")
    body += text(1130, 322, "bilism.org", 15, SKY, "end", weight="700", ls=2)
    return svg(w, h, body, "mcp-mqtt", "TRON-style banner: broker hub emblem with publish and subscribe arrows, mcp-mqtt wordmark")


def icon_svg() -> str:
    w = 512
    body = (f'<rect width="{w}" height="{w}" rx="96" fill="url(#bg)"/><rect width="{w}" height="{w}" rx="96" fill="url(#g2)"/>'
            f'<rect x="10" y="10" width="492" height="492" rx="88" fill="none" stroke="{CY}" stroke-opacity="0.45" stroke-width="6"/>'
            + emblem(256, 256, 0.9))
    return svg(w, w, body, "mcp-mqtt icon", "Broker hub emblem with publish and subscribe arrows")


def favicon_svg() -> str:
    body = (f'<rect width="64" height="64" rx="12" fill="{BG}"/>'
            f'<polygon points="{hexpts(32, 32, 17)}" fill="none" stroke="{CY}" stroke-width="4" stroke-linejoin="round"/>'
            f'<circle cx="32" cy="32" r="6" fill="{CY}"/>'
            f'<path d="M3 32H13M9 27L14 32L9 37" fill="none" stroke="{OR}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M51 32H61M56 27L61 32L56 37" fill="none" stroke="{SKY}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
    return svg(64, 64, body, "mcp-mqtt favicon", "Hex hub with in and out arrows")


# ---------------------------------------------------------------- 64px category icons


def _icon(glyph: str, name: str, desc: str) -> str:
    frame = (f'<rect x="4" y="4" width="56" height="56" rx="12" fill="#070d1c" stroke="{CY}" stroke-width="2"/>'
             f'<path d="M20 4V60M36 4V60M4 20H60M4 36H60" stroke="{SKY}" stroke-opacity="0.12" stroke-width="1"/>')
    g = f'<g fill="none" stroke="{CY}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">{glyph}</g>'
    return svg(64, 64, frame + g, name, desc)


def icons() -> dict[str, str]:
    o = f'stroke="{OR}"'
    return {
        "mosquitto": _icon(f'<path d="M14 46V20L32 36L50 20V46"/><circle cx="32" cy="18" r="3" fill="{CY}"/>', "Mosquitto", "Mosquitto broker: M monogram"),
        "emqx": _icon(f'<path d="M16 16L48 48M48 16L16 48"/><circle cx="32" cy="32" r="6" fill="{CY}"/><circle cx="16" cy="16" r="2.5"/><circle cx="48" cy="16" r="2.5"/><circle cx="16" cy="48" r="2.5"/><circle cx="48" cy="48" r="2.5"/>', "EMQX", "EMQX broker: clustered X node mesh"),
        "nanomq": _icon(f'<polygon points="{hexpts(32, 32, 16)}"/><path d="M34 22L27 34H37L30 43" {o}/>', "NanoMQ", "NanoMQ broker: compact hexagon with bolt"),
        "security": _icon(f'<path d="M32 12L50 19V32C50 42 42 49 32 53C22 49 14 42 14 32V19Z"/><path d="M24 33L30 39L41 26" {o}/>', "Security", "Shield with check mark: guard pipeline"),
        "publish": _icon(f'<circle cx="46" cy="32" r="6"/><path d="M12 32H34M28 25L35 32L28 39" {o}/>', "Publish", "Arrow flowing into broker node"),
        "subscribe": _icon('<circle cx="18" cy="32" r="6"/><path d="M28 32H52M45 25L52 32L45 39"/>', "Subscribe", "Arrow flowing out of broker node"),
    }


# ---------------------------------------------------------------- diagram kit


class Dia:
    def __init__(self, w: int, h: int):
        self.w, self.h, self.b = w, h, [canvas(w, h), reticles(10, 10, w - 20, h - 20, 18)]

    def title(self, t: str, sub: str):
        self.b.append(text(32, 44, t, 24, WHITE, family=SANS, weight="700"))
        self.b.append(text(32, 68, sub, 13, MUTED))
        self.b.append(f'<path d="M32 80H{self.w-32}" stroke="{CY}" stroke-opacity="0.3"/>')

    def node(self, x, y, w, h, head, lines=(), accent=CY, fs=12, hs=14):
        self.b.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{PANEL}" fill-opacity="0.92" stroke="{accent}" stroke-width="1.5" filter="url(#glowS)"/>')
        self.b.append(reticles(x, y, w, h, 8, accent, 2))
        self.b.append(text(x + w / 2, y + 22, head, hs, accent, "middle", weight="700"))
        for i, ln in enumerate(lines):
            self.b.append(text(x + w / 2, y + 44 + i * (fs + 6), ln, fs, MUTED if i else "#e2e8f0", "middle"))

    def arrow(self, d: str, color=CY, label=None, lx=0, ly=0, dash=False):
        m = "ao" if color == OR else "ac"
        da = ' stroke-dasharray="7 5"' if dash else ""
        self.b.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"{da} marker-end="url(#{m})" filter="url(#glowS)"/>')
        if label:
            self.b.append(text(lx, ly, label, 12, color, "middle"))

    def raw(self, s: str):
        self.b.append(s)

    def out(self, title, desc) -> str:
        return svg(self.w, self.h, "\n".join(self.b), title, desc)


def architecture() -> str:
    d = Dia(1200, 560)
    d.title("mcp-mqtt architecture", "stdio MCP server per broker; shared guarded core in src/mcp_mqtt")
    d.node(32, 190, 190, 120, "MCP host", ["LLM client", "Claude, IDE agent", "stdio JSON-RPC"], SKY)
    d.raw(f'<rect x="270" y="104" width="480" height="420" fill="none" stroke="{CY}" stroke-opacity="0.5" stroke-dasharray="6 5"/>')
    d.raw(text(286, 126, "mcp-mqtt-<broker>  (FastMCP, server.py)", 13, CY, weight="700"))
    d.node(290, 140, 440, 96, "Tools (server.py)", ["mqtt_publish  mqtt_subscribe", "mqtt_get_retained  mqtt_policy", "mqtt_publish hidden if MQTT_READ_ONLY=1"], CY)
    d.node(290, 258, 210, 106, "security.py", ["topic + allowlist", "QoS / payload caps", "token-bucket rate limit"], OR)
    d.node(520, 258, 210, 106, "config.py", ["Settings.from_env()", "env only, never", "from tool inputs"], SKY)
    d.node(290, 386, 210, 100, "client.py", ["paho-mqtt, short-lived", "connection per call", "publish ack wait 10s"], CY)
    d.node(520, 386, 210, 100, "brokers/*.py", ["mosquitto.py emqx.py", "nanomq.py: extras()", "per-broker tools"], SKY)
    d.node(950, 120, 220, 96, "Mosquitto", ["MQTT 1883 / 8883 TLS", "mosquitto_sys_stats", "reads $SYS/broker/#"], CY)
    d.node(950, 244, 220, 112, "EMQX", ["MQTT + REST admin API", "emqx_stats", "emqx_list_clients", "emqx_list_subscriptions"], CY)
    d.node(950, 384, 220, 112, "NanoMQ", ["MQTT + HTTP API", "nanomq_stats", "nanomq_list_clients"], CY)
    d.arrow("M222 250H270", SKY, "stdio", 246, 240)
    d.arrow("M395 486V508H810V168H950", CY, "MQTT", 870, 200)
    d.arrow("M810 300H950", CY)
    d.arrow("M810 440H950", CY)
    d.arrow("M730 436H770", OR, dash=True)
    d.arrow("M395 364V386", CY)
    d.arrow("M395 236V258", OR, "guard first", 450, 250)
    d.raw(text(860, 548, "extras call broker HTTP APIs (EMQX, NanoMQ)", 11, MUTED, "middle"))
    return d.out("mcp-mqtt architecture", "MCP host talks stdio to a guarded FastMCP server that reaches Mosquitto, EMQX or NanoMQ via paho-mqtt and broker HTTP APIs")


def _chain(d: Dia, y: int, steps, x0=32, bw=196, gap=40):
    for i, (h, ls, c) in enumerate(steps):
        x = x0 + i * (bw + gap)
        d.node(x, y, bw, 112, h, ls, c, fs=11, hs=13)
        if i:
            d.arrow(f"M{x-gap+2} {y+56}H{x-2}", CY)


def publish_flow() -> str:
    d = Dia(1200, 470)
    d.title("publish flow: mqtt_publish", 'every step must pass or the call returns {"ok": false, "error": ...}')
    s = [
        ("1 rate limit", ["RateLimiter.check()", "token bucket", "60 calls/min"], OR),
        ("2 topic", ["validate_publish_topic", "no + # or $SYS", "256 B, 16 levels"], OR),
        ("3 allowlist", ["topic_matches()", "MQTT_PUBLISH_ALLOW", "empty = deny all"], OR),
        ("4 qos + retain", ["validate_qos 0..max_qos", "default max_qos = 1", "retain: ALLOW_RETAIN"], OR),
        ("5 payload", ["encode_publish_payload", "utf8 | base64", "cap 65,536 B decoded"], OR),
    ]
    _chain(d, 110, s, gap=48, bw=188)
    d.node(32, 290, 250, 112, "client.publish", ["short-lived paho connection", "wait_for_publish 10s", "disconnect in finally"], CY, fs=11, hs=13)
    d.node(350, 290, 250, 112, "broker", ["Mosquitto / EMQX / NanoMQ", "QoS 0 or 1 delivery"], SKY, fs=11, hs=13)
    d.node(668, 290, 250, 112, "result JSON", ["{ok:true, published, topic,", "bytes, qos, retain}"], CY, fs=11, hs=13)
    d.node(950, 290, 218, 112, "denied", ["GuardError / BrokerError", "{ok:false, error}", "logged as warning"], OR, fs=11, hs=13)
    d.arrow("M1000 222V256H157V290", CY, "all five pass", 600, 250)
    d.arrow("M282 346H350", CY)
    d.arrow("M600 346H668", CY)
    d.arrow("M475 402V436H1059V402", OR, "any failure", 800, 430, dash=True)
    return d.out("Publish flow", "mqtt_publish passes rate limit, topic, allowlist, qos and retain, payload checks, then publishes via a short-lived paho connection")


def subscribe_flow() -> str:
    d = Dia(1200, 470)
    d.title("subscribe flow: mqtt_subscribe / mqtt_get_retained", "inbound payloads are untrusted data, never instructions")
    s = [
        ("1 rate limit", ["RateLimiter.check()", "shared per-process", "token bucket"], OR),
        ("2 filter", ["validate_subscribe_filter", "valid + / # placement", "length, level limits"], OR),
        ("3 allowlist", ["filter_covered_by()", "MQTT_SUBSCRIBE_ALLOW", "no wildcard escalation"], OR),
        ("4 clamp", ["max_messages <= 100", "wait <= 30 s", "qos <= max_qos"], OR),
        ("5 client.collect", ["subscribe, gather", "stop at n msgs or wait", "disconnect"], CY),
    ]
    _chain(d, 110, s, gap=48, bw=188)
    d.node(32, 290, 250, 112, "render_inbound", ["8,192 B per message", "utf8 or base64", "untrusted: true"], CY, fs=11, hs=13)
    d.node(350, 290, 250, 112, "bound_messages", ["count first, then", "32,768 B total budget", "truncated flag"], CY, fs=11, hs=13)
    d.node(668, 290, 250, 112, "result JSON", ["{ok, filter, count,", "truncated, messages[]}"], CY, fs=11, hs=13)
    d.node(950, 290, 218, 112, "get_retained", ["same guards, qos 0", "keeps retain=true only", "wait default 2 s"], SKY, fs=11, hs=13)
    d.arrow("M1000 222V256H157V290", CY, "messages", 600, 250)
    d.arrow("M282 346H350", CY)
    d.arrow("M600 346H668", CY)
    d.arrow("M918 346H950", SKY)
    return d.out("Subscribe flow", "mqtt_subscribe validates the filter against the allowlist, collects bounded messages, renders them as untrusted data")


def security_pipeline() -> str:
    d = Dia(1200, 600)
    d.title("security pipeline", "deny-by-default layers from src/mcp_mqtt/security.py, config.py and client.py")
    d.raw(text(32, 112, "OUTBOUND  (LLM to broker)", 13, OR, weight="700"))
    out = [
        ("env-only config", ["Settings.from_env()", "no secrets in tools"], SKY),
        ("read-only gate", ["MQTT_READ_ONLY=1", "removes publish"], OR),
        ("rate limit", ["token bucket", "60 / min"], OR),
        ("topic rules", ["no ctrl chars, no +#", "no $ topics"], OR),
        ("allowlist", ["publish_allow", "empty = deny"], OR),
        ("caps", ["qos <= 1, retain off", "payload 64 KiB"], OR),
    ]
    bw, gap = 160, 34
    for i, (h, ls, c) in enumerate(out):
        x = 32 + i * (bw + gap)
        d.node(x, 124, bw, 92, h, ls, c, fs=11, hs=13)
        if i:
            d.arrow(f"M{x-gap+2} 170H{x-2}", CY)
    d.raw(text(32, 262, "TRANSPORT", 13, SKY, weight="700"))
    d.node(32, 274, 340, 92, "TLS + credentials", ["MQTT_TLS=1: CA verify by default", "plaintext creds to remote refused"], SKY, fs=11, hs=13)
    d.node(430, 274, 340, 92, "stateless connections", ["new paho client per call", "random client id, closed in finally"], SKY, fs=11, hs=13)
    d.node(828, 274, 340, 92, "safe errors", ["GuardError text is LLM-safe", "broker errors: class name only"], SKY, fs=11, hs=13)
    d.raw(text(32, 412, "INBOUND  (broker to LLM)", 13, CY, weight="700"))
    inn = [
        ("subscribe filter", ["must be covered by", "subscribe_allow"], OR),
        ("receive cap", ["8,192 B kept per", "message at receive"], CY),
        ("render_inbound", ["utf8 or base64", "untrusted: true"], CY),
        ("bound_messages", ["max 100 messages", "32 KiB response"], CY),
        ("LLM", ["content, never", "instructions"], SKY),
    ]
    bw2, gap2 = 188, 48
    for i, (h, ls, c) in enumerate(inn):
        x = 32 + i * (bw2 + gap2)
        d.node(x, 424, bw2, 92, h, ls, c, fs=11, hs=13)
        if i:
            d.arrow(f"M{x-gap2+2} 470H{x-2}", CY)
    d.raw(text(32, 560, "orange = guard that can reject the request; cyan = bounding; sky = boundary", 11, MUTED))
    return d.out("Security pipeline", "Outbound guards: config, read-only, rate limit, topic rules, allowlist, caps. Inbound: filter cover, receive cap, untrusted rendering, bounds")


# ---------------------------------------------------------------- output


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def rasterize(svg_path: Path, png_path: Path, width: int, height: int | None = None) -> str | None:
    h = ["-h", str(height)] if height else []
    cmds = []
    if shutil.which("rsvg-convert"):
        cmds.append(("rsvg-convert", ["rsvg-convert", "-w", str(width), *h, "-o", str(png_path), str(svg_path)]))
    if shutil.which("inkscape"):
        cmds.append(("inkscape", ["inkscape", str(svg_path), "--export-type=png", f"--export-filename={png_path}",
                                  f"--export-width={width}"]))
    if shutil.which("magick"):
        cmds.append(("magick", ["magick", "-background", "none", "-density", "192", str(svg_path),
                                "-resize", f"{width}x", str(png_path)]))
    for name, cmd in cmds:
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0 and png_path.exists() and png_path.stat().st_size > 512:
            return name
    return None


def main() -> int:
    a, ic, dg = ROOT / "docs/assets", ROOT / "docs/assets/icons", ROOT / "docs/diagrams"
    logo = write(a / "logo.svg", logo_svg())
    icon = write(a / "icon.svg", icon_svg())
    write(a / "favicon.svg", favicon_svg())
    write(ROOT / "assets/logo.svg", logo.read_text(encoding="utf-8"))
    for n, s in icons().items():
        write(ic / f"icon-{n}.svg", s)
    diagrams = {"architecture": architecture(), "publish-flow": publish_flow(),
                "subscribe-flow": subscribe_flow(), "security-pipeline": security_pipeline()}
    for n, s in diagrams.items():
        write(dg / f"{n}.svg", s)
    jobs = [(logo, a / "logo.png", 1200, 360), (icon, a / "icon.png", 512, 512)]
    jobs += [(dg / f"{n}.svg", dg / f"{n}.png", 1200, None) for n in diagrams]
    used = set()
    for s, p, w, h in jobs:
        r = rasterize(s, p, w, h)
        if r is None:
            print(f"no renderer worked for {s.name}", file=sys.stderr)
        else:
            used.add(r)
    print("renderer:", ", ".join(sorted(used)) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
