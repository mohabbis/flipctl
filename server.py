"""
FlipCTL backend server.

Exposes a REST API consumed by both the Web UI and the TUI:
  GET  /api/plugins        → list of all loaded plugins with input schemas
  POST /api/execute        → run a plugin and return its output
  GET  /                   → serve web/index.html
  GET  /static/{filename}  → serve additional static assets (future use)
"""
import asyncio
from functools import partial
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.plugin_manager import PluginError, PluginManager

app = FastAPI(title="FlipCTL", version="0.1.0")

WEB_DIR = Path(__file__).parent / "web"
plugin_manager = PluginManager()


class ExecuteRequest(BaseModel):
    plugin: str
    inputs: dict


@app.get("/api/plugins")
async def list_plugins():
    return JSONResponse(content=plugin_manager.list_plugins())


@app.post("/api/execute")
async def execute_plugin(req: ExecuteRequest):
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, partial(plugin_manager.execute, req.plugin, req.inputs)
        )
        return JSONResponse(content=result)
    except PluginError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/")
async def serve_ui():
    index = WEB_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Web UI not found")
    return FileResponse(index)


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
