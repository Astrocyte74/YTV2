#!/bin/bash
# Dashboard Status Script

echo "=== YTV2 Dashboard Status ==="
echo ""

# Check if container is running
if docker ps --format '{{.Names}}' | grep -q ytv2-dashboard; then
    echo "Status: ✓ Running"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAMES|dashboard"
    echo ""
    echo "URLs:"
    echo "  Local:     http://localhost:10000"
    echo "  Tailscale: http://marks-macbook-pro-2.tail9e123c.ts.net:10000/"
    echo ""
    echo "Asset version:"
    curl -s http://localhost:10000/ | grep -o 'dashboard_v3.js?v=[^"]*' | head -1
else
    echo "Status: ✗ Not running"
    echo ""
    echo "Run ./restart.sh to start"
fi
