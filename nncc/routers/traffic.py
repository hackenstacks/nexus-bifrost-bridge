"""
NeXuS Command Center - Traffic API Router
Endpoints for traffic monitoring and statistics
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Optional
import asyncio
import json

from models import (
    TrafficEvent,
    TrafficStats,
    HAProxyStats,
    LiveTrafficRequest,
)
from services import traffic_monitor

router = APIRouter(prefix="/traffic", tags=["traffic"])


@router.get("/stats", response_model=TrafficStats)
async def get_traffic_stats():
    """
    Get current traffic statistics.

    Returns aggregate traffic data including:
    - Total bytes in/out
    - Active connections
    - Per-network breakdown
    - Uptime
    """
    return traffic_monitor.get_stats()


@router.get("/live", response_model=List[TrafficEvent])
async def get_live_traffic(
    limit: int = 100,
    networks: Optional[str] = None
):
    """
    Get recent traffic events.

    Args:
        limit: Maximum number of events to return (default 100)
        networks: Comma-separated list of network IDs to filter by
    """
    network_list = networks.split(',') if networks else None
    return traffic_monitor.get_events(limit=limit, networks=network_list)


@router.get("/haproxy", response_model=List[HAProxyStats])
async def get_haproxy_stats():
    """
    Get HAProxy backend statistics.

    Returns detailed stats for each backend server including:
    - Current/total sessions
    - Bytes transferred
    - Health check status
    - Response times
    """
    return traffic_monitor.get_haproxy_stats()


@router.websocket("/ws")
async def websocket_traffic(websocket: WebSocket):
    """
    WebSocket endpoint for real-time traffic updates.

    Streams traffic statistics at regular intervals.
    Send JSON messages to control the stream:
    - {"action": "pause"} - Pause updates
    - {"action": "resume"} - Resume updates
    - {"action": "filter", "networks": ["tor", "i2p"]} - Filter by networks
    """
    await websocket.accept()

    paused = False
    filter_networks: Optional[List[str]] = None

    async def send_update(data: dict):
        if paused:
            return
        try:
            if filter_networks:
                # Filter per_network stats
                filtered_data = data.copy()
                if "stats" in filtered_data:
                    per_network = filtered_data["stats"].get("per_network", {})
                    filtered_data["stats"]["per_network"] = {
                        k: v for k, v in per_network.items()
                        if k in filter_networks
                    }
            else:
                filtered_data = data

            await websocket.send_json(filtered_data)
        except Exception:
            pass

    # Subscribe to traffic updates
    traffic_monitor.subscribe(send_update)

    try:
        # Send initial stats
        await websocket.send_json({
            "type": "initial",
            "stats": traffic_monitor.get_stats().model_dump(mode='json'),
        })

        while True:
            try:
                # Handle incoming messages with timeout
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # Heartbeat timeout
                )

                try:
                    data = json.loads(message)
                    action = data.get("action")

                    if action == "pause":
                        paused = True
                        await websocket.send_json({"type": "ack", "status": "paused"})

                    elif action == "resume":
                        paused = False
                        await websocket.send_json({"type": "ack", "status": "resumed"})

                    elif action == "filter":
                        filter_networks = data.get("networks")
                        await websocket.send_json({
                            "type": "ack",
                            "status": "filter_set",
                            "networks": filter_networks
                        })

                    elif action == "ping":
                        await websocket.send_json({"type": "pong"})

                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    finally:
        traffic_monitor.unsubscribe(send_update)


@router.get("/by-network/{network_id}")
async def get_network_traffic(network_id: str):
    """
    Get traffic statistics for a specific network.
    """
    stats = traffic_monitor.get_stats()
    network_stats = stats.per_network.get(network_id)

    if not network_stats:
        return {
            "network_id": network_id,
            "bytes_in": 0,
            "bytes_out": 0,
            "connections": 0,
            "note": "No traffic data available"
        }

    return network_stats
