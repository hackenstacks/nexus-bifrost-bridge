"""
NeXuS Heimdall Router — proxy to heimdall_server.py at :7474
Exposes: /api/heimdall/{stats,services,connections,vpn,faces/events}
Camera WebSocket connects direct to :7474 (WS proxy not wired here).
"""

import os
import httpx
from fastapi import APIRouter, HTTPException, WebSocket

router = APIRouter(prefix="/heimdall", tags=["heimdall"])

HEIMDALL = os.environ.get("HEIMDALL_API", "http://127.0.0.1:7474")
_CLIENT  = httpx.AsyncClient(base_url=HEIMDALL, timeout=10.0)


async def _proxy(path: str):
    try:
        r = await _CLIENT.get(f"/api/heimdall/{path}")
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        raise HTTPException(503, detail="heimdall_server offline — start ~/NeXuS/projects/nexus-heimdall/heimdall.sh")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@router.get("/stats")
async def stats():
    return await _proxy("stats")


@router.get("/services")
async def services():
    return await _proxy("services")


@router.get("/connections")
async def connections():
    return await _proxy("connections")


@router.get("/vpn")
async def vpn():
    return await _proxy("vpn")


@router.get("/faces/events")
async def face_events():
    return await _proxy("faces/events")


@router.get("/status")
async def status():
    """Quick liveness check — returns heimdall_server up/down."""
    try:
        r = await _CLIENT.get("/api/heimdall/stats", timeout=2.0)
        return {"online": r.status_code == 200}
    except Exception:
        return {"online": False}
