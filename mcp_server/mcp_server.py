import json
import os, re
import httpx
import traceback
import settings
from typing import Dict, Any
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from opensearchpy import OpenSearch

# ----------------------------
# OpenSearch Client Setup
# ----------------------------

client = OpenSearch(
    hosts=[{"host": settings.OPENSEARCH["host"], "port": settings.OPENSEARCH["port"]}],
    http_auth=(settings.OPENSEARCH["username"], settings.OPENSEARCH["password"]),
    use_ssl=True,
    verify_certs = True,
)

# ----------------------------
# MCP Functions
# ----------------------------

def metadata_search(job_id: int = None, index: str = None, limit: int = 10):
    """Search the OpenSearch index panda OS index for jobs by job_id or title."""
    if index is None:
        index = settings.INDICES["completed"]

    query = {"query": {"match_all": {}}}
    if job_id:
        query = {"query": {"match": {"pandaid": job_id}}}

    response = client.search(index=index, body=query, size=limit)
    results = {}
    for hit in response['hits']['hits']:
        source = hit['_source']
        results.update(source)
    return {"result": results, "total": len(results), "error": ""}

def get_source_document_raw(filepath_relative: str):
    """Retrieve raw document or logs from a JSON file."""
    try:
        full_path = os.path.join(os.getcwd(), filepath_relative)
        with open(full_path, "r") as f:
            document = json.load(f)
        return {"result": document}
    except Exception as e:
        return {"result": None, "error": str(e)}

def log_query(path: str, tail: int = -1):
    """
    Fetch logs from a URL or local file and return the last `tail` lines.
    Returns a dict with 'lines' and 'error'.
    """
    try:
        if path.startswith("http://") or path.startswith("https://"):
            with httpx.Client() as client:
                resp = client.get(path, timeout=30)
                resp.raise_for_status()
                log_text = resp.text
        else:
            with open(path, "r") as f:
                log_text = f.read()

        lines = log_text.strip().splitlines()
        return {"result": lines[-tail:], "error": ""}

    except httpx.HTTPStatusError as e:
        return {"result": [], "error": f"HTTP error {e.response.status_code}: {str(e)}"}
    except httpx.RequestError as e:
        return {"result": [], "error": f"Request failed: {str(e)}"}
    except FileNotFoundError:
        return {"result": [], "error": f"File not found: {path}"}
    except Exception as e:
        return {"result": [], "error": f"Unexpected error: {str(e)}"}

def update_AI_index(document: dict, index_name: str = settings.INDICES["knn"]):
    """
    Update or insert a document into kNN index only.
    """
    if index_name != settings.INDICES["knn"]:
        return {"error": "Updating indices other than 'AI-index' is forbidden"}

    if not isinstance(document, dict):
        return {"error": "Document must be a dictionary"}

    if "id" not in document and "job_id" not in document:
        return {"error": "Document must include 'id' or 'job_id'"}

    try:
        doc_id = document.get("id")
        response = client.index(index=index_name, id=doc_id, body=document)
        return {"result": response}
    except Exception as e:
        return {"error": str(e)}

# ----------------------------
# MCP Dispatcher
# ----------------------------
def call_mcp_function(function_name: str, arguments: dict):
    if function_name == "functions.metadata_search":
        return metadata_search(**arguments)
    elif function_name == "functions.get_source_document_raw":
        return get_source_document_raw(**arguments)
    elif function_name == "functions.log_query":
        return log_query(**arguments)
    elif function_name == "functions.update_AI_index":
        return update_AI_index(**arguments)
    else:
        return {"error": f"Unknown function: {function_name}"}

# ----------------------------
# FastAPI Server Setup
# ----------------------------
app = FastAPI(title="Custom MCP Server")

# ----------------------------
# API Key Setup
# ----------------------------
API_KEY = settings.MCP_API["key"]
API_KEY_NAME = settings.MCP_API["name"]
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header != API_KEY:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key_header

# ----------------------------
# Request/Response Models
# ----------------------------
class MCPRequest(BaseModel):
    function_name: str
    arguments: Dict[str, Any]

class MCPResponse(BaseModel):
    result: Dict[str, Any]

# ----------------------------
# Protected Endpoint
# ----------------------------
@app.post("/call_function", response_model=MCPResponse)
async def call_function(req: MCPRequest, api_key: str = Depends(get_api_key)):
    try:
        result = call_mcp_function(req.function_name, req.arguments)
        return {"result": result}
    except Exception as e:
        print("Exception in call_function:", repr(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}

# ----------------------------
# Optional standalone test
# ----------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mcp_server:app", host="0.0.0.0", port=8000, reload=True)

