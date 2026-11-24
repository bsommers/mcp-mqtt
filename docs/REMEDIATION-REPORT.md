# mcp-mqtt: Review and Remediation Report

Date: 2026-11-22 · Commit reviewed: `f2fb00c` (main) · Scope: all of `src/`, `tests/`, `docker/`, `.github/`, `pyproject.toml`, docs.
Method: full read of the ~800 source lines, plus `ruff`, `mypy --strict`, `pytest --cov`, and runtime reproduction of suspected defects. Lenses: pr-review core lenses (correctness, breaking changes, error handling, test coverage, trust boundaries), security, dependencies, CI, architecture.
Integration tests (31) were skipped: no docker brokers were running.

## 1. Verdict: useful or toy?

**Useful, with a solid core, not a toy. It is a pre-1.0 project, though, and a few gaps keep it from production use.**

For:
- The security model is real and not decorative: deny-by-default allowlists, wildcard-escalation checks (`filter_covered_by`), `$SYS` handling, payload caps checked before decode, a token-bucket rate limiter, credentials only from the environment, stdio-only transport, a refusal to send passwords in plaintext off-loopback, and inbound payloads flagged `untrusted`.
- Quality signals are good: ruff (including bandit `S` rules) is clean. `security.py` and `config.py` have 100% line and branch coverage. 243 unit tests pass, there are docker integration tests against three real brokers, and GitHub Actions are pinned by SHA.
- It fills a real niche: governed MQTT access for LLM agents, with the allowlist as the key feature. A generic MQTT MCP wrapper would hand an agent the whole broker.

Against:
- Config parsing fails open on two security switches (R-01).
- The broker-extras code (EMQX, NanoMQ) has 0% test coverage outside docker, and the two files are copy-pasted (R-05, R-08).
- There is no CI for tests or lint, and `mypy --strict` reports 19 errors (R-06).
- The server is not packaged or published, so adoption friction is high (R-10).

## 2. Findings

Severity: **H** fix before wider use · **M** should fix · **L** polish.

| ID | Sev | Area | Finding |
|----|-----|------|---------|
| R-01 | H | config | **Fail-open boolean parsing.** `MQTT_READ_ONLY`, `MQTT_TLS`, `MQTT_TLS_INSECURE` and `MQTT_ALLOW_RETAIN` are true only for the literal `"1"`. Reproduced: `MQTT_READ_ONLY=true` gives `read_only=False`, so `mqtt_publish` is registered. `MQTT_TLS=true` gives plaintext. An operator who believes the server is read-only or encrypted is wrong, silently. `config.py:51-67` |
| R-02 | M | trust boundary | **Untrusted data from the broker REST APIs is unmarked.** `emqx_list_clients` and `emqx_list_subscriptions` return client IDs, usernames and topics. Any MQTT client can set these, so they are a prompt-injection channel. Unlike `render_inbound`, nothing flags or bounds individual fields, and a nested JSON blob is passed through. `emqx.py:46-52`, `nanomq.py` |
| R-03 | M | trust boundary | **Cleartext REST credentials.** `EMQX_API_URL` and `NANOMQ_API_URL` accept `http://` to any host, and Basic-auth credentials are sent unencrypted. The MQTT side has this guard (`config.py:76`); the REST side does not. |
| R-04 | M | availability | **Sync tools block the event loop.** `emqx_*`, `nanomq_*` and `mqtt_policy` are plain `def` tools. FastMCP runs them inline, so the blocking `httpx` call (up to 5 s, plus streaming) stalls every concurrent tool call. The MQTT tools correctly use `asyncio.to_thread`. |
| R-05 | M | maintainability | **`emqx.py` and `nanomq.py` duplicate `_base_url` and `_get`** (about 50 lines each). A fix to one, such as R-02 or R-03, must be mirrored by hand. |
| R-06 | M | process | **No CI for tests or lint.** The only workflow is `pages.yml`. The "gate" (ruff, pytest) is run only on the author's machine. `mypy --strict` gives 19 errors (untyped `extras` callbacks, untyped decorators, bare `dict`). The checkpoint says the mypy and 85% branch-coverage gates were never run. |
| R-07 | M | correctness | **`mqtt_get_retained` can miss retained messages.** It collects up to `max_messages` of *any* message and filters retained afterwards. On a busy filter, live messages fill the quota first. It also waits the full time window instead of stopping once the retained burst ends. Already noted in CHECKPOINT. |
| R-08 | M | test coverage | `brokers/*.py` have 0% unit coverage and `client.py` 16% without docker. Total unit-only coverage is 58%. Error paths (non-200 status, truncation, bad URL, missing credentials, connect timeout, subscribe failure) are not mocked. |
| R-09 | L | correctness | **Reported `bytes` is wrong for oversized messages.** `collect` truncates payloads to `max_message_bytes+1` on receipt, so `render_inbound` reports `bytes: 8193` for a 1 MB message. The truncated flag is right, but the size is misleading. `client.py:75`, `security.py:158` |
| R-10 | L | correctness | **Truncation can split a UTF-8 character.** The text payload then fails to decode and is returned as base64. Reproduced: `"aé"` with a 2-byte cap gives `base64`. Use `errors="ignore"` on a trailing partial sequence, or back off to a char boundary. `security.py:147-153` |
| R-11 | L | error handling | **Non-`BrokerError` exceptions escape.** `_new_client` runs outside the `_connect` try. A bad `MQTT_TLS_CA` or key path raises `FileNotFoundError` or `ssl.SSLError` out of the tool, and the filesystem path may leak to the LLM in the error text. Wrap in `BrokerError` with a generic message. On connect timeout or failure, `c.disconnect()` is not called, so a socket may leak. `client.py:18-47` |
| R-12 | L | observability | **Hand-rolled JSON log format** (`server.py:35`) does not escape `%(message)s`. A `"` in a logged value, such as a subscribe filter containing one, breaks the JSON line or allows log forging. Use a real JSON formatter. |
| R-13 | L | config | **Limits are only partly validated or exposed.** `max_wait_seconds`, `max_topic_length` and `max_topic_levels` have no env var. There is no check that `max_message_bytes <= max_response_bytes`, and no port-range check. `MQTT_MAX_QOS` is clamped silently. `MQTT_TLS_INSECURE=1` gives no startup warning. `mqtt_policy` omits several limits. |
| R-14 | L | correctness | `mosquitto_sys_stats` does not clamp `wait_seconds` from below (the other tools use `max(0.1, …)`). A zero or negative value returns immediately. `mosquitto.py:26` |
| R-15 | L | code quality | Dead branch in `validate_publish_topic`: `if "" in levels[:-1] …: pass` (`security.py:36-37`). Remove it, or decide whether empty topic levels should be rejected. |
| R-16 | L | dependencies | `httpx>=0.27` has no upper bound and is a hard dependency even for Mosquitto-only users. Dev dependencies are unpinned (the lockfile covers them). There is no `pip-audit` or Dependabot. `pyproject.toml:6,14` |
| R-17 | L | packaging | `pyproject.toml` has no license, readme, authors, URLs or classifiers. There are no `[project.optional-dependencies]` for the broker extras that the docs call "extras". There is no PyPI release and no `uvx` one-liner, and no Dockerfile. `README` install path is clone-and-run. |
| R-18 | L | docker/test infra | Test images use floating or loose tags (`eclipse-mosquitto:2`). Test broker credentials (NanoMQ `admin/public`, EMQX defaults) are fine on loopback but should carry a louder "never expose" comment in `nanomq.conf`. |
| R-19 | L | docs | The static test counts drift: README says 274, the site says 270, and the current run is 243 passed + 31 skipped. `docs/CHECKPOINT.md` is an untracked working note, so commit or ignore it. |
| R-20 | L | design | **Per-process, in-memory rate limit.** It resets on restart, and denied requests consume tokens (fine as a flood guard, but document it). There is no audit log of `publish` payload hashes. |

### Prompt-injection note (inherent, not a bug)
`untrusted: true` is a field the model may ignore. For high-assurance use, offer an optional mode that wraps the payload in explicit delimiters, or returns metadata (topic, size, hash) and requires a second call for the body. Document that allowlists, not flags, are the real control.

## 3. Remediation plan

**Phase 1: correctness and security (about 0.5 day)**
1. R-01: add a strict `_bool(name)` accepting `1/true/yes/on` and `0/false/no/off/""`, and raising `ValueError` on anything else. Add tests for every switch.
2. R-03: in the REST helpers, reject non-loopback `http://` when credentials are set, mirroring `Settings.validate`.
3. R-02: wrap REST results as `{"untrusted": true, "data": …}`, truncate string fields, and mention it in the tool docstrings.
4. R-04: make the extras `async` with `asyncio.to_thread`.
5. R-11: catch `OSError` and `ssl.SSLError` in `_new_client` and `_connect`, raise `BrokerError` with a generic message, and `disconnect()` in all paths.

**Phase 2: structure and gates (about 1 day)**
6. R-05: extract `brokers/_rest.py` (`rest_get(settings, limiter, base_env, auth_env, path)`), with a thin profile per broker.
7. R-06: add `.github/workflows/ci.yml`: `ruff`, `mypy --strict`, `pytest -m "not integration" --cov-fail-under=85`, plus an integration job using the docker compose brokers. Use least-privilege `permissions: contents: read`, and pin actions by SHA like `pages.yml`. Fix the 19 mypy errors by typing `extras` as `Callable[[FastMCP, Settings, RateLimiter], None]`.
8. R-08: add `respx` or `httpx.MockTransport` tests for the REST helpers, and a fake `paho` client for `client.py`.
9. R-16: add `pip-audit` (or Dependabot) to CI, cap `httpx<1`, and move `httpx` into an `emqx`/`nanomq` extra.

**Phase 3: behavior polish (about 0.5 day)**
10. R-07: in `collect`, add a `retained_only` flag. Stop on the first non-retained message, or after a short quiet period.
11. R-09, R-10: track the true size in `on_message`, and cut on a UTF-8 boundary.
12. R-12, R-13, R-14, R-15, R-19: JSON log formatter, expose the remaining limits, validate limit relationships, warn on `TLS_INSECURE`, remove the dead branch, and generate the test counts rather than hardcoding them.

**Phase 4: adoption**
13. R-17: complete the metadata and publish to PyPI so `uvx mcp-mosquitto` works. Add a minimal Dockerfile. Tag `v0.1.0` and add a release workflow.
14. Add `docs/SECURITY.md` threat-model entries for R-02, R-20 and the prompt-injection note. Add a Claude Desktop and Claude Code config example that uses read-only plus narrow allowlists as the recommended default.

## 4. Suggested improvements beyond fixes
- MQTT 5 features: user properties and content type in the rendered messages, and request/response correlation.
- Optional TLS client-cert-only auth example, and a tested Mosquitto/EMQX ACL recipe. Broker-side ACLs should back the MCP allowlist, so both layers hold.
- A `mqtt_list_topics` discovery tool, bounded and restricted to the allowlist, for agents that don't know the topic tree.
- An optional persistent connection with a bounded ring buffer, for use cases where short-lived connections miss data between calls.
- A `--check-config` command that prints the effective policy and warnings. That would have caught R-01.

## 5. What was not verified
- The 31 docker integration tests were not run. No brokers were up.
- No live MCP client round-trip was done.
- The Pages site was not rendered.
- `pip-audit` / CVE scan of the lockfile was not run; do this in CI (R-16).
