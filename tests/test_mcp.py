import requests
import json, re
import numpy as np

raw_vector = np.random.rand(768).tolist()
def normalize(vec):
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist() if norm != 0 else vec
normalized_vector = normalize(np.array(raw_vector))
kNN_index = "FIXME"
completed_index = "FIXME"
running_index = "FIXME"

# ----------------------------
# MCP Server Configuration
# ----------------------------
MCP_SERVER_URL = "http://localhost:8000/call_function"

# ----------------------------
# Helper function to call MCP
# ----------------------------
def call_mcp_function(function_name: str, arguments: dict):
    """
    Calls a MCP server function and returns the result.
    """
    payload = {
        "function_name": function_name,
        "arguments": arguments
    }

    headers = {
        "access_token": "FIXME"  # API key
    }

    try:
        response = requests.post(MCP_SERVER_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("result", None)
    except requests.HTTPError as e:
        return {"error": f"HTTP error: {e}"}
    except requests.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except json.JSONDecodeError as e:
        return {"error": f"Failed to decode JSON: {e}"}

# ----------------------------
# Example usage
# ----------------------------
if __name__ == "__main__":
    pandaid=53551225
    # Example metadata search
    metadata = call_mcp_function(
        "functions.metadata_search",
        {"job_id": pandaid, "index": completed_index}
    )
    print(f"metadata: {metadata}\n")
    print("MCP Sever Response:")
    print(json.dumps(metadata, indent=2))

    # Example log query
    pilotid = metadata['result'].get('pilotid')
    match = re.search(r"(.*)\bpilotlog.txt\b", pilotid)
    if match:
        url = match.group(1) + "payload.stderr"
    log = call_mcp_function(
        "functions.log_query",
        {"path": url}
        #{"path": url, "tail": 200}
    )
    print(f"log: {log['result']}\n")
    print("MCP Sever Response:")
    print(json.dumps(log, indent=2))

    # Example document to update AI-index
    doc = {
        "id": 1,
        "pandaid": 53551225,
        "statechangetime": "2025-08-06 17:29:50",
        "job_summary": "Reco step failed with exit code 137",
        "job_summary_vector": normalized_vector
    }
    result = call_mcp_function(
        "functions.update_AI_index",
        {"document": doc, "index_name": "panda_k-nn_test"}
    )
    print("MCP Sever Response:")
    print(json.dumps(result, indent=2))

