#!/usr/bin/env sh
set -eu

# 1) FastMCP on :8000
uv run python app/app.py \
  --transport streamable-http \
  --host 0.0.0.0 \
  --port 8000 &

# 2) oauth2-proxy front-end on :4180
exec oauth2-proxy \
  --http-address 0.0.0.0:4180 \
  --upstream http://localhost:8000 \
  --skip-auth-route '^/\.well-known/.*$' \
  --skip-auth-route '^/register$' \
  --email-domain "$OAUTH2_PROXY_EMAIL_DOMAINS" \
  --client-id "$OAUTH2_PROXY_CLIENT_ID" \
  --client-secret "$OAUTH2_PROXY_CLIENT_SECRET" \
  --redirect-url "$OAUTH2_PROXY_REDIRECT_URL" \
  --cookie-secret "$OAUTH2_PROXY_COOKIE_SECRET" \
  --cookie-expire 24h \
  --skip-provider-button
