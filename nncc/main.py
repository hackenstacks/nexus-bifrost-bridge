#!/usr/bin/env python3
"""
🌀 NeXuS Command Center
Unified control plane for anonymity networks

A FastAPI-based backend providing:
- REST API for network control
- Real-time traffic monitoring via WebSocket
- Dynamic routing configuration
- Health monitoring for all networks
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from config import settings
from routers import (
    networks_router,
    routing_router,
    traffic_router,
    health_router,
    vpn_router,
    netcheck_router,
    heimdall_router,
    screenrec_router,
)
from services import (
    health_checker,
    rules_manager,
    traffic_monitor,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    logger.info("🌀 NeXuS Command Center starting...")

    # Load configuration
    await rules_manager.load()
    logger.info("✅ Rules loaded")

    # Start background services
    await health_checker.start()
    logger.info("✅ Health checker started")

    await traffic_monitor.start()
    logger.info("✅ Traffic monitor started")

    # Start file watching for config changes
    await rules_manager.start_watching()
    logger.info("✅ Config watcher started")

    logger.info("🚀 NeXuS Command Center ready!")
    logger.info(f"   API: http://{settings.host}:{settings.api_port}/api")
    logger.info(f"   Docs: http://{settings.host}:{settings.api_port}/docs")

    yield  # Application runs here

    # Shutdown
    logger.info("🛑 NeXuS Command Center shutting down...")

    await rules_manager.stop_watching()
    await traffic_monitor.stop()
    await health_checker.stop()
    await rules_manager.save()

    logger.info("👋 NeXuS Command Center stopped")


# Create FastAPI application
app = FastAPI(
    title="🌀 NeXuS Command Center",
    description="""
    Unified control plane for anonymity networks.

    ## Features
    - **Network Control**: Start, stop, restart Tor, I2P, Yggdrasil, Reticulum
    - **Smart Routing**: Domain-based routing with bypass rules
    - **Traffic Monitoring**: Real-time traffic visualization
    - **Health Checks**: Continuous network health monitoring

    ## Networks Supported
    - 🧅 **Tor** - 6-node pool with HAProxy load balancing
    - 🟣 **I2P** - Anonymous eepsite access
    - 🟢 **Yggdrasil** - IPv6 mesh network
    - 🔴 **Reticulum** - Resilient communications
    - 🦇 **BATMAN-adv** - Mesh networking
    - 🔓 **Direct** - Bypass rules for direct access
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to dashboard origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(networks_router, prefix="/api")
app.include_router(routing_router, prefix="/api")
app.include_router(traffic_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(vpn_router, prefix="/api")
app.include_router(netcheck_router, prefix="/api")
app.include_router(heimdall_router, prefix="/api")
app.include_router(screenrec_router, prefix="/api")


# Root endpoint
@app.get("/api")
async def api_root():
    """API root - returns available endpoints"""
    return {
        "name": "NeXuS Command Center API",
        "version": "1.0.0",
        "endpoints": {
            "networks": "/api/networks",
            "routing": "/api/routing",
            "traffic": "/api/traffic",
            "health": "/api/health",
            "docs": "/docs",
        },
        "websocket": {
            "traffic": "/api/traffic/ws",
        }
    }


# Static file serving for web dashboard
static_dir = Path(__file__).parent
if (static_dir / "index.html").exists():
    # Serve static files
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def serve_dashboard():
        """Serve the web dashboard"""
        return FileResponse(static_dir / "index.html")

    @app.get("/{path:path}")
    async def serve_static(path: str):
        """Serve static files or fallback to index.html"""
        file_path = static_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(static_dir / "index.html")


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=404,
            content={"error": "Not found", "path": str(request.url.path)}
        )
    # For non-API routes, serve dashboard (SPA routing)
    if (static_dir / "index.html").exists():
        return FileResponse(static_dir / "index.html")
    return JSONResponse(status_code=404, content={"error": "Not found"})


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.error(f"Server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
