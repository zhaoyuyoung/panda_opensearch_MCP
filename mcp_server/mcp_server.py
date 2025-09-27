# Standard library
import os
import json
import traceback

# Third-party
import anyio
from pydantic import BaseModel, Field
from typing import Optional, Union, List, Dict, Any
from opensearchpy import OpenSearch, exceptions
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

from config import HOST, PORT, USER, PASSWORD, ALLOWED_INDEX, COMPLETED_INDEX, VALID_TOKEN

# -----------------------------------------
# OpenSearch Client
# -----------------------------------------
def get_opensearch_client():
    """Returns a configured OpenSearch client instance."""
    return OpenSearch(
        hosts=[{'host': HOST, 'port': PORT}],
        http_auth=(USER, PASSWORD),
        use_ssl=True,
        verify_certs=True
    )

# Get the client instance
OPENSEARCH_CLIENT = get_opensearch_client()


# -----------------------------------------
# PYDANTIC SCHEMAS (For Tool Input/Output)
# -----------------------------------------
class DocumentToStore(BaseModel):
    """Schema for the job data to be indexed."""
    
    pandaid: int = Field(
        description="The unique identifier for the job."
    )
    
    statechangetime: str = Field(
        description="The timestamp when the job's state last changed (e.g., '2025-08-06 17:29:50')."
    )
    
    job_summary: str = Field(
        description="A brief description of the job's final status or error."
    )
    
    job_summary_vector: List[float] = Field(
        description="The normalized vector representation of the job summary."
    )
    
    index_name: str = Field(
        default=ALLOWED_INDEX,
        description="The name of the OpenSearch index to use for this data."
    )

class SearchQuery(BaseModel):
    """Schema for the search operation."""
    index_name: str = Field(description="The name of the OpenSearch index to search.")
    query: str = Field(description="The plain text query string to search for in the document 'content'.")
    limit: int = Field(default=10, description="The maximum number of search results to return.")


# -----------------------------------------
# FASTMCP SERVER INITIALIZATION 
# -----------------------------------------
auth_provider = StaticTokenVerifier(tokens=VALID_TOKEN)
mcp = FastMCP(
    name="OpenSearchAgent",
    instructions="I provide tools to index and search documents in an OpenSearch cluster.",
    auth=auth_provider
)


# -----------------------------------------
# OpenSearch customized MCP tools
# -----------------------------------------
def _metadata_search_sync(
    job_id: Optional[Union[int, List[int]]] = None,
    task_id: Optional[Union[int, List[int]]] = None,
    req_id: Optional[Union[int, List[int]]] = None,
    index: Optional[str] = None,
    limit: int = 10,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Synchronous helper to search documents in OpenSearch metadata index.
    """
    # Convert single ints to lists
    if isinstance(job_id, int):
        job_id = [job_id]
    if isinstance(task_id, int):
        task_id = [task_id]
    if isinstance(req_id, int):
        req_id = [req_id]

    # Default index
    if index is None:
        index = COMPLETED_INDEX

    # Merge filters
    all_filters = {
        "pandaid": job_id,
        "jeditaskid": task_id,
        "reqid": req_id,
        **(filters or {})
    }

    # Must have at least one primary filter
    if not any(all_filters.get(k) is not None for k in ["pandaid", "jeditaskid", "reqid"]):
        return {"result": [], "total": 0, "error": "At least one of job_id, task_id, or req_id must be provided."}

    # Build query
    must_clauses = []
    for field, value in all_filters.items():
        if value is None:
            continue
        must_clauses.append({"terms": {field: value}} if isinstance(value, list) else {"match": {field: value}})

    query_body = {"query": {"bool": {"must": must_clauses}}} if must_clauses else {"query": {"match_all": {}}}

    try:
        response = OPENSEARCH_CLIENT.search(index=index, body=query_body, size=limit)
    except Exception as e:
        return {"result": [], "total": 0, "error": f"OpenSearch Error: {type(e).__name__} - {e}"}

    results = [hit.get("_source", {}) for hit in response.get("hits", {}).get("hits", [])]
    return {"result": results, "total": len(results), "error": ""}


@mcp.tool()
async def metadata_search_tool(
    job_id: Optional[Union[int, List[int]]] = None,
    task_id: Optional[Union[int, List[int]]] = None,
    req_id: Optional[Union[int, List[int]]] = None,
    index: Optional[str] = None,
    limit: int = 10,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Searches documents in the metadata OpenSearch index.

    Performs a filtered search based on job_id, task_id, req_id, and optional additional filters.
    Converts single integer IDs into lists internally for consistent querying.

    Parameters:
        job_id (int | List[int], optional): PanDA job IDs to filter.
        task_id (int | List[int], optional): PanDA Task IDs to filter.
        req_id (int | List[int], optional): Workflow Request IDs to filter.
        index (str, optional): OpenSearch index to query. Defaults to 'completed' index from settings.
        limit (int): Maximum number of results to return. Default is 10.
        filters (dict, optional): Additional filters as field-value mappings.

    Returns:
        dict: {
            "result": List of documents (dict),
            "total": Number of documents returned,
            "error": Error message if any, else empty string
        }

    Notes:
        - At least one of job_id, task_id, or req_id must be provided; otherwise returns an error.
        - Runs the blocking OpenSearch search in a background thread for async safety.
    """
    import anyio
    return await anyio.to_thread.run_sync(
        _metadata_search_sync,
        job_id,
        task_id,
        req_id,
        index,
        limit,
        filters
    )


def _get_source_document_raw_sync(filepath_relative: str) -> Dict[str, Optional[Any]]:
    """Synchronous core logic for reading and parsing a local JSON file."""
    try:
        full_path = os.path.join(os.getcwd(), filepath_relative)
        
        # Blocking I/O: Reading the local file
        with open(full_path, "r") as f:
            document = json.load(f)
            
        return {"result": document, "error": None}
        
    except FileNotFoundError:
        return {"result": None, "error": f"Error: File not found at '{filepath_relative}'."}
    except json.JSONDecodeError:
        return {"result": None, "error": f"Error: File at '{filepath_path}' is not valid JSON."}
    except Exception as e:
        return {"result": None, "error": f"Unexpected error reading file: {type(e).__name__} - {str(e)}"}
    

@mcp.tool
async def get_source_document_tool(
    filepath_relative: str
) -> Dict[str, Optional[Any]]:
    """
    Retrieve and parse a raw document from a local JSON file on the server.

    :param filepath_relative: Relative path to the JSON file from the server's working directory.
    :return: A dictionary containing 'result' (the parsed JSON content) or 'error' (an error message).
    """
    # Use anyio.to_thread.run_sync to safely execute the blocking file I/O
    # in a background thread without blocking the async event loop.
    return await anyio.to_thread.run_sync(
        _get_source_document_raw_sync,
        filepath_relative
    )


def _log_query_sync(path: str, tail: int = -1) -> Dict[str, Union[List[str], str]]:
    """Synchronous core logic for fetching logs."""
    import httpx
    try:
        # Fetch log from URL
        if path.startswith("http://") or path.startswith("https://"):
            with httpx.Client() as client:
                resp = client.get(path, timeout=30)
                resp.raise_for_status()
                log_text = resp.text
        else:
            # Read local file (Blocking I/O)
            with open(path, "r") as f:
                log_text = f.read()

        lines = log_text.strip().splitlines()
        
        # Return last `tail` lines
        return {"result": lines[-tail:], "error": ""}
    
    # All original error handling remains in the synchronous function
    except httpx.HTTPStatusError as e:
        return {"result": [], "error": f"HTTP error {e.response.status_code}: {str(e)}"}
    except httpx.RequestError as e:
        return {"result": [], "error": f"Request failed: {str(e)}"}
    except FileNotFoundError:
        return {"result": [], "error": f"File not found: {path}"}
    except Exception as e:
        return {"result": [], "error": f"Unexpected error: {str(e)}"}
    

@mcp.tool()
async def log_query_tool(
    path: str, 
    tail: int = -1
) -> Dict[str, Union[List[str], str]]:
    """
    Fetch logs from a URL or local file and return the last 'tail' lines.
    
    This is useful for analyzing recent activity in a system log or checking an external status file.

    :param path: Path to the log file on the server, or a URL (http/https) to fetch logs from.
    :param tail: Number of last lines to return. Default -1 returns all lines.
    :return: A dictionary with 'result' (a list of log lines) and 'error' (an error message, or empty string).
    """
    # Safely execute the blocking I/O function in a background thread
    return await anyio.to_thread.run_sync(
        _log_query_sync,
        path,
        tail
    )
    

def _index_document_sync(data: DocumentToStore) -> str:
    """
    Synchronous helper to index a document into OpenSearch.
    Creates the index if it doesn't exist.
    """
    try:
        # Ensure only the allowed AI index can be updated
        if data.index_name != ALLOWED_INDEX:
            return f"Error: Updating indices other than '{ALLOWED_INDEX}' is forbidden"

        # Ensure index exists
        if not OPENSEARCH_CLIENT.indices.exists(index=data.index_name):
            OPENSEARCH_CLIENT.indices.create(index=data.index_name)

        # Index the document
        document = data.dict(exclude={'index_name'})
        response = OPENSEARCH_CLIENT.index(
            index=data.index_name,
            id=data.pandaid,
            body=document,  # use 'document=' for modern OpenSearch client
            refresh=True         # make it immediately searchable
        )

        doc_id = response['_id']
        return f"Document successfully indexed into index '{data.index_name}' with ID: {doc_id}."

    except exceptions.ConnectionError:
        return f"Error: Could not connect to OpenSearch at {HOST}:{PORT}. Check server logs."
    except Exception as e:
        return f"An error occurred during indexing: {type(e).__name__} - {e}"


@mcp.tool()
async def index_document_tool(index_name: str, data: DocumentToStore) -> str:
    """
    Indexes a new document into a specified OpenSearch index.

    This tool creates the index if it doesn't exist, and indexes the document 
    using the fields provided in `data`. Only a pre-defined allowed index 
    (`ALLOWED_INDEX`) can be used; attempts to index into any other index 
    will return an error.

    Parameters:
        data (DocumentToStore): A Pydantic model containing:
            - title (str): The main title of the document.
            - content (str): The body or main text of the document.
            - index_name (str, optional): The OpenSearch index to use.

    Returns:
        str: A status message indicating whether the document was successfully 
             indexed or if an error occurred.

    Raises:
        Exceptions are handled internally and returned as informative strings.
    """
    import anyio
    return await anyio.to_thread.run_sync(_index_document_sync, data)


def _update_document_sync(
    index_name: str,
    document_id: str,
    update_data: Dict[str, Any]
) -> str:
    """
    Synchronous helper to partially update a document in OpenSearch.
    Mirrors the logic of the original async function.
    """
    try:
        # Enforcement of allowed index
        if index_name != ALLOWED_INDEX:
            return f"Error: Updating indices other than '{ALLOWED_INDEX}' is forbidden"

        # Ensure 'doc' key exists for partial update
        body = update_data if 'doc' in update_data else {"doc": update_data}

        # Perform the update
        response = OPENSEARCH_CLIENT.update(
            index=index_name,
            id=document_id,
            body=body,
            refresh=True
        )

        # Process result
        result = response.get('result', 'unknown')
        if result == 'updated':
            return f"Document ID '{document_id}' in index '{index_name}' successfully updated. New version: {response['_version']}"
        elif result == 'noop':
            return f"Document ID '{document_id}' in index '{index_name}' was not updated (no changes detected)."
        else:
            return f"Update operation for Document ID '{document_id}' resulted in: {result}"

    except exceptions.NotFoundError:
        return f"Error: Document with ID '{document_id}' not found in index '{index_name}'."
    except exceptions.ConnectionError:
        return f"Error: Could not connect to OpenSearch. Check server logs."
    except Exception as e:
        return f"An error occurred during document update: {type(e).__name__} - {e}"


@mcp.tool()
async def update_document_tool(
    index_name: str,
    document_id: str,
    update_data: Dict[str, Any]
) -> str:
    """
    Partially updates an existing document in a specified OpenSearch index.

    This tool performs a partial update of a document identified by `document_id` 
    in `index_name`. The update payload should be provided in `update_data`. 
    For partial updates, it is typically structured as:

        {"doc": {"field_to_change": "new_value"}}

    If the 'doc' key is missing, the tool automatically wraps `update_data` in a 'doc' key.

    Index update is restricted to a pre-defined allowed index (`ALLOWED_INDEX`). 
    Attempting to update any other index will return an error message.

    Parameters:
        index_name (str): The OpenSearch index containing the document.
        document_id (str): The unique ID of the document to update.
        update_data (Dict[str, Any]): The fields to update. Typically in {"doc": {...}} format.

    Returns:
        str: A status message indicating the outcome of the update operation, e.g., 
             successful update, no changes detected, or an error description.

    Raises:
        Handled internally: NotFoundError, ConnectionError, or other exceptions will return 
        informative error messages rather than raising.
    """
    return await anyio.to_thread.run_sync(
        _update_document_sync,
        index_name,
        document_id,
        update_data
    )


if __name__ == "__main__":
    # Run the MCP server over SSE (HTTP-based transport)
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    print(f"OpenSearch FastMCP SSE server running on http://{host}:{port}")
    mcp.run(transport="sse", host=host, port=port)
