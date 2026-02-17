#!/bin/bash
# Dashboard Restart Script
# Run from i9 Mac to restart the dashboard server

set -e
cd /Users/markdarby16/16projects/ytv2/dashboard16

echo "Stopping dashboard..."
docker-compose down 2>/dev/null || true

echo "Starting dashboard..."
docker-compose up -d

sleep 2

# Verify it's running
if docker ps | grep -q ytv2-dashboard; then
    echo "Dashboard running at: http://localhost:10000"
    echo "Tailscale URL: http://marks-macbook-pro-2.tail9e123c.ts.net:10000/"
    echo ""
    echo "Asset versions:"
    curl -s http://localhost:10000/ | grep -o 'dashboard_v3.js?v=[^"]*' | head -1
else
    echo "ERROR: Dashboard failed to start"
    docker logs ytv2-dashboard --tail 20
    exit 1
fi
