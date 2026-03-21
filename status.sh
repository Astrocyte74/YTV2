#!/bin/bash
# Dashboard Status Script

DOCKER_BIN="${DOCKER_BIN:-$(command -v docker 2>/dev/null || echo /usr/local/bin/docker)}"

echo "=== YTV2 Dashboard Status ==="
echo ""

# Check if container is running
if "$DOCKER_BIN" ps --format '{{.Names}}' | grep -q ytv2-dashboard; then
    echo "Status: ✓ Running"
    "$DOCKER_BIN" ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAMES|dashboard"
    echo ""
    echo "URLs:"
    echo "  Local:     http://localhost:10000"
    echo "  Tailscale: http://marks-macbook-pro-2.tail9e123c.ts.net:10000/"
    echo ""
    echo "Asset version:"
    curl -s http://localhost:10000/ | grep -o '/static/dashboard_v3.js?v=[^"]*' | head -1
    echo "Mode:"
    if "$DOCKER_BIN" inspect ytv2-dashboard --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}' 2>/dev/null | grep -q '/app/static'; then
        echo "  Development (bind mounts enabled)"
    else
        echo "  Production (image-backed code)"
    fi
else
    echo "Status: ✗ Not running"
    echo ""
    echo "Run ./restart.sh to start"
fi
