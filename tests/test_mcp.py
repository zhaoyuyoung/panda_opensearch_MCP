import json, re
import numpy as np
import asyncio, anyio
from fastmcp.client import Client

kNN_index = "test_knn"
completed_index = "test_completed"
running_index = "test_running"
TOKEN = "test_token"
MCP_SERVER_URL = "http://localhost:8000/sse"  # or your LoadBalancer IP

# ----------------------------
# Helper function to call MCP
# ----------------------------
async def call_mcp_function(function_name: str, arguments: dict):
    """
    Call an MCP server function with exception handling.
    """
    try:
        async with Client(MCP_SERVER_URL, auth=TOKEN) as client:
            return await client.call_tool(function_name, arguments)
    except asyncio.TimeoutError:
        return {"error": "Request timed out"}
    except OSError as e:
        return {"error": f"Connection error: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}

# ----------------------------
# Example usage
# ----------------------------
def normalize(vec):
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist() if norm != 0 else vec
raw_vector = np.random.rand(768).tolist()
normalized_vector = normalize(np.array(raw_vector))

async def main():
    pandaid=53551225
    # Example metadata search
    metadata = await call_mcp_function(
        "metadata_search_tool",
        {"job_id": pandaid, "index": completed_index}
    )
    print(f"metadata: {metadata}\n")
    
    # Example log query
    docs = metadata.structured_content.get("result", [])
    if docs:
        pilotid = docs[0].get('pilotid')
    match = re.search(r"(.*)\bpilotlog.txt\b", pilotid)
    if match:
        url = match.group(1) + "payload.stderr"
    log = await call_mcp_function(
        "log_query_tool",
        {"path": url}
        #{"path": url, "tail": 200}
    )
    print(f"log: {log.structured_content.get('result', [])}\n")
    
    # Example document to update AI-index
    doc = {
        "pandaid": pandaid,
        "statechangetime": "2025-08-06 17:29:50",
        "job_summary": "Reco step failed with exit code 137",
        "job_summary_vector": normalized_vector
    }
    result = await call_mcp_function(
        "update_document_tool",
        {"index_name": kNN_index, "document_id": "1", "update_data": doc}
    )
    print(f"MCP Sever Response: {result}\n")

    # Example document to index AI-index
    result = await call_mcp_function(
        "index_document_tool",
        {"index_name": kNN_index, "data": doc}
    )
    print(f"MCP Sever Response: {result}\n")
    

if __name__ == "__main__":
    asyncio.run(main())
