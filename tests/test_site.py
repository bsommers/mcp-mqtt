"""Static checks for the GitHub Pages site in docs/."""

import re
import time
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
INDEX = DOCS / "index.html"
ROOT = DOCS.parent


def _wait_for_assets() -> None:
    deadline = time.time() + 180
    while time.time() < deadline:
        missing = [p for p in _local_refs() if not (DOCS / p).exists()]
        if not missing:
            return
        time.sleep(5)


def _html() -> str:
    return INDEX.read_text(encoding="utf-8")


def _local_refs() -> list[str]:
    refs = re.findall(r'(?:src|href)="([^"]+)"', _html())
    skip = ("http://", "https://", "mailto:", "#", "javascript:")
    return [r.split("#")[0] for r in refs if r and not r.startswith(skip)]


def test_nojekyll_present():
    assert (DOCS / ".nojekyll").exists()


def test_no_broken_relative_links():
    _wait_for_assets()
    broken = [r for r in _local_refs() if r and not (DOCS / r).exists()]
    assert not broken, broken


def test_open_graph_and_icon():
    html = _html()
    for tag in ("og:title", "og:description", "og:image"):
        assert f'property="{tag}"' in html
    assert re.search(r'<link rel="icon"[^>]*href="assets/icon\.svg"', html)
    assert 'content="assets/logo.png"' in html


def test_no_external_scripts_or_cdn():
    html = _html()
    for src in re.findall(r'<script[^>]*\ssrc="([^"]+)"', html):
        assert not src.startswith(("http:", "https:", "//")), src
    for href in re.findall(r'<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"', html):
        assert not href.startswith(("http:", "https:", "//")), href
    assert "@import" not in (DOCS / "site.css").read_text()


def test_counts_match_repo():
    html = _html()
    tools = set()
    for f in (ROOT / "src").rglob("*.py"):
        tools.update(re.findall(r"@mcp\.tool\(\)\s+(?:async )?def (\w+)", f.read_text()))
    import subprocess
    import sys

    out = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--ignore=tests/test_site.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    tests = sum(1 for line in out.splitlines() if "::" in line)
    # slack covers this file's own tests, which are excluded from the collected count
    m = re.search(r"<b>(\d+)</b>tools", html)
    assert m and int(m.group(1)) == len(tools)
    t = re.search(r"<b>(\d+)</b>tests", html)
    assert t and abs(int(t.group(1)) - tests) <= 10
