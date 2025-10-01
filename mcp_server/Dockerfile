# Use a lightweight Python base
FROM python:3.11-slim

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install tini for proper signal handling
RUN apt-get update && apt-get install -y tini \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create app directory and copy code
RUN mkdir -p /opt/os_mcp_server
COPY . /opt/os_mcp_server

# Copy startup script
COPY start.sh /opt/os_mcp_server/start.sh
RUN chmod +x /opt/os_mcp_server/start.sh

# Use tini as init process and start our script
ENTRYPOINT ["/usr/bin/tini", "--"]

# Start both MCP server and REST wrapper
CMD ["/opt/os_mcp_server/start.sh"]
