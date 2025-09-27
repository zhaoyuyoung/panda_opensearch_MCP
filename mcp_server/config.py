"""
config.py

Configuration constants derived from settings.py for OpenSearch + MCP server.
"""

import time
from typing import Dict, Any
import settings

# -----------------------------
# OpenSearch connection
# -----------------------------
HOST: str = settings.OPENSEARCH["host"]
PORT: int = settings.OPENSEARCH["port"]
USER: str = settings.OPENSEARCH["username"]
PASSWORD: str = settings.OPENSEARCH["password"]

# -----------------------------
# Indices
# -----------------------------
ALLOWED_INDEX: str = settings.INDICES["knn"]
COMPLETED_INDEX: str = settings.INDICES["completed"]
RUNNING_INDEX: str = settings.INDICES["running"]

# -----------------------------
# MCP server secret & token
# -----------------------------
SERVER_SECRET: str = settings.MCP_API["key"]

VALID_TOKEN: Dict[str, Dict[str, Any]] = {
    SERVER_SECRET: {
        "expires_at": 9999999999,  # far future timestamp
        "user_id": "OpenSearchUser-1",
        "client_id": "OpenSearchClient-1",
        "token": SERVER_SECRET
    }
}

# -----------------------------
# Helper function
# -----------------------------
def is_token_valid(token: str) -> bool:
    """
    Returns True if token exists in VALID_TOKEN and is not expired.
    """
    token_data = VALID_TOKEN.get(token)
    if not token_data:
        return False
    return token_data.get("expires_at", 0) > int(time.time())
