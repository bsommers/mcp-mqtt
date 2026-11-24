#!/usr/bin/env bash
# Generate a random, throwaway EMQX API key for the local test broker (never committed).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p emqx
if [ ! -f emqx/api-keys.txt ]; then
  umask 077
  printf 'mcp-test-key:%s\n' "$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)" > emqx/api-keys.txt
fi
IFS=: read -r key secret _ < emqx/api-keys.txt
echo "export EMQX_API_URL=http://localhost:18083 EMQX_API_KEY=$key EMQX_API_SECRET=$secret"
