"""
FlipCTL backend server.

Exposes a REST API consumed by both the Web UI and the TUI:
  GET  /api/plugins        → list of all loaded plugins with input schemas
  POST /api/execute        → run a plugin and return its output
  GET  /                   → serve web/index.html
  GET  /static/{filename}  → serve additional static assets (future use)
  GET  /health             → health check endpoint
"""
import asyncio
import time
from collections import defaultdict, deque
from functools import partial
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.plugin_manager import PluginError, PluginManager
from core.logging import logger
from core.config import config

app = FastAPI(title="FlipCTL", version="0.2.0")

# Configuration from config system
API_KEY = config.get("api_key")
ENABLE_AUTH = config.get("enable_auth", False)
ENABLE_RATE_LIMITING = config.get("enable_rate_limit", True)
RATE_LIMIT_REQUESTS = config.get("rate_limit_requests", 10)
RATE_LIMIT_WINDOW = config.get("rate_limit_window", 60)

# Rate tracking
request_history = defaultdict(lambda: deque(maxlen=1000))

WEB_DIR = Path(__file__).parent / "web"
plugin_manager = PluginManager()
security = HTTPBearer(auto_error=False)


class ExecuteRequest(BaseModel):
    plugin: str
    inputs: dict


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def check_rate_limit(request: Request):
    """Check if the client has exceeded the rate limit."""
    if not ENABLE_RATE_LIMITING:
        return True

    client_ip = get_client_ip(request)
    now = time.time()

    # Clean old entries
    request_times = request_history[client_ip]
    while request_times and request_times[0] <= now - RATE_LIMIT_WINDOW:
        request_times.popleft()

    # Check if limit exceeded
    if len(request_times) >= RATE_LIMIT_REQUESTS:
        logger.warning(f"Rate limit exceeded for IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds."
        )

    # Add current request
    request_times.append(now)
    logger.debug(f"Request from {client_ip} ({len(request_times)}/{RATE_LIMIT_REQUESTS})")
    return True


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key if authentication is enabled."""
    if not ENABLE_AUTH:
        return True

    if not credentials:
        logger.warning("Missing API key in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not API_KEY or credentials.credentials != API_KEY:
        logger.warning(f"Invalid API key attempt from {get_client_ip(request)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug("API key validation successful")
    return True


@app.get("/api/plugins")
async def list_plugins(request: Request, _: bool = Depends(check_rate_limit)):
    """List all available plugins."""
    logger.debug("Plugins list requested")
    return JSONResponse(content=plugin_manager.list_plugins())


@app.post("/api/execute")
async def execute_plugin(
    request: Request,
    req: ExecuteRequest,
    _: bool = Depends(check_rate_limit),
    __: bool = Depends(verify_api_key)
):
    """Execute a plugin with given inputs."""
    client_ip = get_client_ip(request)
    logger.info(f"Executing plugin '{req.plugin}' from {client_ip} with inputs: {list(req.inputs.keys())}")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, partial(plugin_manager.execute, req.plugin, req.inputs)
        )
        logger.info(f"Plugin '{req.plugin}' executed successfully from {client_ip}")
        return JSONResponse(content=result)
    except PluginError as exc:
        logger.warning(f"Plugin execution failed for {client_ip}: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as e:
        logger.error(f"Unexpected error executing plugin {req.plugin} from {client_ip}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/")
async def serve_ui(request: Request, _: bool = Depends(check_rate_limit)):
    """Serve the web interface."""
    logger.debug("Serving UI")
    index = WEB_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Web UI not found")
    return FileResponse(index)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.debug("Health check requested")
    return JSONResponse(content={
        "status": "healthy",
        "version": "0.2.0",
        "auth_enabled": ENABLE_AUTH,
        "rate_limit": f"{RATE_LIMIT_REQUESTS}/{RATE_LIMIT_WINDOW}s" if RATE_LIMIT_REQUESTS else "disabled",
        "plugins_loaded": len(plugin_manager.list_plugins()),
        "config_loaded": bool(config._config)
    })


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")