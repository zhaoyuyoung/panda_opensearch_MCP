#!/bin/bash
set -e

cd /opt/os_mcp_server

# Function to handle termination signals
terminate() {
    echo "Termination signal received, stopping processes..."
    if [ ! -z "$MCP_PID" ]; then
        kill -SIGTERM "$MCP_PID"
        wait "$MCP_PID"
    fi
    if [ ! -z "$UVICORN_PID" ]; then
        kill -SIGTERM "$UVICORN_PID"
        wait "$UVICORN_PID"
    fi
    exit 0
}

# Trap SIGTERM and SIGINT signals
trap terminate SIGTERM SIGINT

# Start MCP server in background
python mcp_server.py &
MCP_PID=$!
echo "MCP server started with PID $MCP_PID"

# Start REST wrapper in foreground
uvicorn rest_wrapper:app --host 0.0.0.0 --port 9000 &
UVICORN_PID=$!
echo "REST wrapper started with PID $UVICORN_PID"

# Wait for either process to exit
wait -n $MCP_PID $UVICORN_PID

# If any process exits, terminate the other
terminate

