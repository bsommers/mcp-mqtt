"""Rewrite the static test count in README badge and docs/index.html from `pytest --collect-only`.

Run after adding tests:  uv run python scripts/update_counts.py   (--check exits 1 on drift)
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
INDEX = ROOT / "docs" / "index.html"


def collected() -> int:
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--ignore=tests/test_site.py"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    ).stdout
    return sum(1 for line in out.splitlines() if "::" in line)


def main() -> int:
    n = collected()
    subs = [(README, r"tests-\d+%20passing", f"tests-{n}%20passing"),
            (INDEX, r"<b>\d+</b>tests", f"<b>{n}</b>tests")]
    drift = False
    for path, pat, repl in subs:
        text = path.read_text()
        new = re.sub(pat, repl, text)
        if new != text:
            drift = True
            if "--check" not in sys.argv:
                path.write_text(new)
    print(f"collected={n} drift={drift}")  # noqa: T201
    return 1 if drift and "--check" in sys.argv else 0


if __name__ == "__main__":
    sys.exit(main())
