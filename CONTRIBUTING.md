# Contributing

## Setup

```bash
export UV_CACHE_DIR=/datanapps/uv-cache UV_PROJECT_ENVIRONMENT=/datanapps/venvs/mcp-mqtt   # optional: keep caches off /tmp
uv sync
docker compose -f docker/docker-compose.yml up -d      # optional: integration tests
```

## Before sending a change

```bash
uv run ruff check .
uv run mypy src
uv run pytest
```

Integration tests skip brokers that are not running. See [docs/TESTING.md](docs/TESTING.md).

## Rules that must hold

- stdout is JSON-RPC only: no `print()` in `src/` (a test enforces it).
- Tool parameters never carry credentials or policy; configuration comes from the environment (a test enforces it).
- Keep deny-by-default: new capabilities need an explicit opt-in setting.
- Bound anything that grows from untrusted input.
- Handlers doing blocking I/O must use `asyncio.to_thread`.
- When you change an env var, default, tool or behaviour, update `README.md`, `docs/` and `CHANGELOG.md` in the same change, and check names and defaults against the code.
