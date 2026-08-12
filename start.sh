#!/bin/bash
# Starts the web server + Cloudflare Tunnel together.
# Usage: bash start.sh [--run-now]

set -e
cd "$(dirname "$0")"

RUN_NOW=""
if [[ "$1" == "--run-now" ]]; then
  RUN_NOW="--run-now"
fi

echo "Starting Market Digest server..."
python run.py $RUN_NOW &
SERVER_PID=$!

# Wait for server to be ready
echo "Waiting for server to start..."
until curl -s http://localhost:8000/health > /dev/null 2>&1; do sleep 1; done

echo "Server is up. Starting Cloudflare Tunnel..."
cloudflared tunnel --url http://localhost:8000 &
TUNNEL_PID=$!

echo ""
echo "✅ Market Digest is running."
echo "   Local:  http://localhost:8000"
echo "   Public: Check the cloudflared output above for your public URL"
echo ""
echo "Press Ctrl+C to stop everything."

# Wait and clean up on exit
trap "kill $SERVER_PID $TUNNEL_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait
