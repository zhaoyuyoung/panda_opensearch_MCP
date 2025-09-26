import os

def get_env(name: str, default: str | None = None) -> str | None:
    """Helper to fetch environment variables with an optional default."""
    return os.getenv(name, default)

# OpenSearch connection
OPENSEARCH = {
    "host": get_env("OPENSEARCH_HOST", "localhost"),
    "port": int(get_env("OPENSEARCH_PORT", "9200")),
    "username": get_env("OPENSEARCH_USER", "admin"),
    "password": get_env("OPENSEARCH_PASS", "admin"),
}

# Index names
INDICES = {
    "knn": get_env("KNN_INDEX", "knn-index"),
    "completed": get_env("COMPLETED_INDEX", "completed-index"),
    "running": get_env("RUNNING_INDEX", "running-index"),
}

# MCP API
MCP_API = {
    "key": get_env("API_KEY", "api-key"),
    "name": get_env("API_KEY_NAME", "api-key-name")
}
