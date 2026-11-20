# Test brokers (loopback only, anonymous)

`docker compose -f docker/docker-compose.yml up -d`

| Broker | MQTT | HTTP API |
|---|---|---|
| mosquitto | 127.0.0.1:21883 | - |
| emqx | 127.0.0.1:21884 | 127.0.0.1:18083 |
| nanomq | 127.0.0.1:21885 | 127.0.0.1:8081 |

EMQX API key is bootstrapped from `docker/emqx/api-keys.txt` (test-only). Set:

    EMQX_API_URL=http://localhost:18083 EMQX_API_KEY=mcp-test-key EMQX_API_SECRET=<generated: see docker/init-test-env.sh>

NanoMQ (credentials from `docker/nanomq/nanomq.conf`):

    NANOMQ_API_URL=http://localhost:8081 NANOMQ_API_USER=admin NANOMQ_API_PASSWORD=public
