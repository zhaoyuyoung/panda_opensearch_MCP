# rest_wrapper.py
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastmcp.client import Client
import asyncio

MCP_SERVER_URL = "http://localhost:8000/sse"

app = FastAPI()


# ----------------------------
# Tool call request model
# ----------------------------
class ToolCallRequest(BaseModel):
    tool_name: str
    payload: dict


# ----------------------------
# Extract token from Authorization header
# ----------------------------
async def get_auth_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header"
        )
    return auth_header.split(" ", 1)[1]



# ----------------------------
# Helper function to safely call MCP
# ----------------------------
async def safe_call_mcp(coroutine):
    try:
        return await coroutine
    except asyncio.TimeoutError:
        return {"error": "Request timed out"}
    except OSError as e:
        return {"error": f"Connection error: {e}"}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}


# ----------------------------
# List all tools
# ----------------------------
@app.get("/list_tools")
async def list_tools_rest(token: str = Depends(get_auth_token)):
    async with Client(MCP_SERVER_URL, auth=token) as client:
        tools = await safe_call_mcp(client.list_tools())

    # Convert Tool objects to dicts if needed
    if isinstance(tools, list):
        result = []
        for t in tools:
            if hasattr(t, "name") and hasattr(t, "description"):
                result.append({
                    "name": getattr(t, "name"),
                    "description": getattr(t, "description"),
                })
            else:
                result.append(t)

        return JSONResponse(content={"result": result})

    return JSONResponse(content={"result": tools})


# ----------------------------
# Call a specific tool
# ----------------------------
@app.post("/call_tool")
async def call_tool_rest(
    req: ToolCallRequest, 
    token: str = Depends(get_auth_token)
):
    async with Client(MCP_SERVER_URL, auth=token) as client:
        call_result = await safe_call_mcp(
            client.call_tool(req.tool_name, req.payload)
        )

    # Convert CallToolResult to dict
    if hasattr(call_result, "result") or hasattr(call_result, "error"):
        return {
            "result": getattr(call_result, "result", None),
            "error": getattr(call_result, "error", None),
        }

    # fallback if already a dict
    return {"result": call_result}