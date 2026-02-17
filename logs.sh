#!/bin/bash
# Dashboard Logs Script
# Usage: ./logs.sh [lines] [-f for follow]
# Examples:
#   ./logs.sh        # Last 50 lines
#   ./logs.sh 100    # Last 100 lines
#   ./logs.sh -f     # Follow (live tail)

LINES=${1:-50}

if [ "$1" = "-f" ]; then
    echo "Following dashboard logs (Ctrl+C to stop)..."
    docker logs ytv2-dashboard --tail 50 -f
elif [ "$2" = "-f" ]; then
    echo "Following dashboard logs (Ctrl+C to stop)..."
    docker logs ytv2-dashboard --tail "$LINES" -f
else
    echo "=== Last $LINES dashboard log lines ==="
    docker logs ytv2-dashboard --tail "$LINES"
fi
