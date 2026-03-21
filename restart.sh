#!/bin/bash
# Dashboard production restart script
# Rebuilds the image so code/template/static changes are baked into the container.

set -e
cd /Users/markdarby16/16projects/ytv2/dashboard16

DOCKER_BIN="${DOCKER_BIN:-$(command -v docker 2>/dev/null || echo /usr/local/bin/docker)}"
DOCKER_COMPOSE_BIN="${DOCKER_COMPOSE_BIN:-$(command -v docker-compose 2>/dev/null || echo /usr/local/bin/docker-compose)}"

echo "Rebuilding and recreating dashboard..."
"$DOCKER_COMPOSE_BIN" up -d --build --force-recreate dashboard

sleep 3

# Verify it's running
if "$DOCKER_BIN" ps | grep -q ytv2-dashboard; then
    echo "Dashboard running at: http://localhost:10000"
    echo "Tailscale URL: http://marks-macbook-pro-2.tail9e123c.ts.net:10000/"
    echo ""
    echo "Asset versions:"
    curl -s http://localhost:10000/ | grep -o '/static/dashboard_v3.js?v=[^"]*' | head -1
    echo ""
    echo "Tip: for live-edit development use:"
    echo "  $DOCKER_COMPOSE_BIN -f docker-compose.yml -f docker-compose.dev.yml up -d dashboard"
else
    echo "ERROR: Dashboard failed to start"
    "$DOCKER_BIN" logs ytv2-dashboard --tail 20
    exit 1
fi
