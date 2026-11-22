# Testing

[← Back to Project README](../README.md) · [Docs index](README.md)

## Layout

| File | Kind | What it covers |
|---|---|---|
| `tests/test_security.py` | unit | Topic validation, allowlist matching/coverage, QoS, payload encode/caps, rate limiter, `render_inbound`, `bound_messages` |
| `tests/test_config.py` | unit | Env parsing, defaults, startup validation |
| `tests/test_server_unit.py` | unit | Tool handlers with the broker client stubbed |
| `tests/test_client.py` | unit | `client.py` against a fake paho client: connect/TLS errors, cleanup, `retained_only`, true message size |
| `tests/test_rest.py` | unit | EMQX/NanoMQ REST helper via `httpx.MockTransport`: status, truncation, https guard, sanitising |
| `tests/test_static_gates.py` | static | AST gates: no `print()` in `src/` (MCP-008); no credential-named tool parameters (MCP-001) |
| `tests/test_integration.py` | integration (`-m integration`) | Spawns the real stdio server per broker and runs publish/subscribe round trips, retained, denials, oversize, rate limit, `mosquitto_sys_stats` |

Integration tests parametrize over mosquitto (21883), emqx (21884) and nanomq (21885) and **skip** a broker whose port is closed, so they never fail merely because Docker is down.

## Commands

```bash
export UV_CACHE_DIR=/datanapps/uv-cache UV_PROJECT_ENVIRONMENT=/datanapps/venvs/mcp-mqtt   # optional, keeps caches off /tmp
uv sync
docker compose -f docker/docker-compose.yml up -d     # test brokers, anonymous, loopback only
uv run pytest                                          # everything; integration tests run if brokers are up
uv run pytest -m "not integration"                     # unit + static only
uv run pytest -m integration                           # integration only
uv run ruff check .
uv run mypy src --strict
uv run pytest -m "not integration" --cov=src/mcp_mqtt --cov-branch   # CI gate: >= 85%
```

Test counts are generated, not hand-edited: run `uv run python scripts/update_counts.py` to refresh the README badge and site figure. CI (`.github/workflows/ci.yml`) runs ruff, `mypy --strict`, the unit suite with an 85% branch-coverage gate, `pip-audit`, and the docker integration job.

## Coverage

Unit tests alone reach about 98% line+branch coverage of `src/mcp_mqtt`: `client.py` is tested against a fake paho client and the REST helpers via `httpx.MockTransport`. The integration tests run the server in a subprocess over stdio, so they add confidence but not coverage numbers.

## Test brokers

`docker/docker-compose.yml` runs `eclipse-mosquitto:2`, `emqx/emqx:5.8.0` and `emqx/nanomq:0.23.0-slim`, bound to `127.0.0.1` with anonymous access. They are for testing only; never expose them. REST helper tests need `EMQX_API_URL/EMQX_API_KEY/EMQX_API_SECRET` or `NANOMQ_API_URL/NANOMQ_API_USER/NANOMQ_API_PASSWORD` as listed in [`docker/README.md`](../docker/README.md).

## Adding tests

Guard logic: add a pure unit test in `tests/test_security.py`. A new env var: extend `tests/test_config.py`. A new tool: add a stubbed test in `tests/test_server_unit.py` and an integration case; the static gates pick up new `@mcp.tool()` functions automatically.
