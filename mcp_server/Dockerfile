# Use a lightweight Python base
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Create the app directory
RUN mkdir -p /opt/os_mcp_server
COPY . /opt/os_mcp_server

ENTRYPOINT ["sh", "-c", "cd /opt/os_mcp_server && exec \"$@\"", "--"]

# Run MCP server
CMD ["python", "mcp_server.py"]