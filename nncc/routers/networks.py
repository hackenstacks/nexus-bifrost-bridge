"""
NeXuS Command Center - Networks API Router
Endpoints for network status and control
"""

import asyncio
from fastapi import APIRouter, HTTPException
from typing import List

from config import settings
from models import (
    Network,
    NetworkStatus,
    NetworkAction,
    NetworkActionRequest,
    NetworkActionResponse,
    NetworkConfigUpdate,
)
from services import container_service, health_checker

router = APIRouter(prefix="/networks", tags=["networks"])


@router.get("", response_model=List[Network])
async def list_networks():
    """List all configured networks with current status — parallel container checks."""

    async def _build_network(network_id, config):
        containers = await container_service.get_network_containers(network_id)
        health = health_checker.get_health(network_id)
        running_containers = sum(1 for c in containers if c.running)
        total_containers = len(config.get("containers", []))
        if total_containers == 0:
            status = NetworkStatus.UP
        elif running_containers == 0:
            status = NetworkStatus.DOWN
        elif running_containers < total_containers:
            status = NetworkStatus.DEGRADED
        else:
            status = NetworkStatus.UP
        if health and health.status != NetworkStatus.UNKNOWN:
            status = health.status
        return Network(
            id=network_id,
            name=config.get("name", network_id),
            icon=config.get("icon", "🌐"),
            color=config.get("color", "#808080"),
            status=status,
            health=health,
            containers=containers,
            latency_ms=health.latency_ms if health else None,
        )

    networks = await asyncio.gather(
        *[_build_network(nid, cfg) for nid, cfg in settings.networks.items()]
    )

    return networks


@router.get("/{network_id}", response_model=Network)
async def get_network(network_id: str):
    """
    Get detailed information about a specific network.
    """
    if network_id not in settings.networks:
        raise HTTPException(status_code=404, detail=f"Network '{network_id}' not found")

    config = settings.networks[network_id]
    containers = await container_service.get_network_containers(network_id)
    health = health_checker.get_health(network_id)

    running_containers = sum(1 for c in containers if c.running)
    total_containers = len(config.get("containers", []))

    if total_containers == 0:
        status = NetworkStatus.UP
    elif running_containers == 0:
        status = NetworkStatus.DOWN
    elif running_containers < total_containers:
        status = NetworkStatus.DEGRADED
    else:
        status = NetworkStatus.UP

    if health and health.status != NetworkStatus.UNKNOWN:
        status = health.status

    return Network(
        id=network_id,
        name=config.get("name", network_id),
        icon=config.get("icon", "🌐"),
        color=config.get("color", "#808080"),
        status=status,
        health=health,
        containers=containers,
        latency_ms=health.latency_ms if health else None,
    )


@router.post("/{network_id}/start", response_model=NetworkActionResponse)
async def start_network(network_id: str):
    """
    Start all containers for a network.
    """
    if network_id not in settings.networks:
        raise HTTPException(status_code=404, detail=f"Network '{network_id}' not found")

    result = await container_service.perform_action(network_id, NetworkAction.START)

    return NetworkActionResponse(
        success=result["success"],
        message=result["message"],
        network_id=network_id,
        action=NetworkAction.START,
        affected_containers=result["affected_containers"],
    )


@router.post("/{network_id}/stop", response_model=NetworkActionResponse)
async def stop_network(network_id: str):
    """
    Stop all containers for a network.
    """
    if network_id not in settings.networks:
        raise HTTPException(status_code=404, detail=f"Network '{network_id}' not found")

    result = await container_service.perform_action(network_id, NetworkAction.STOP)

    return NetworkActionResponse(
        success=result["success"],
        message=result["message"],
        network_id=network_id,
        action=NetworkAction.STOP,
        affected_containers=result["affected_containers"],
    )


@router.post("/{network_id}/restart", response_model=NetworkActionResponse)
async def restart_network(network_id: str):
    """
    Restart all containers for a network.
    """
    if network_id not in settings.networks:
        raise HTTPException(status_code=404, detail=f"Network '{network_id}' not found")

    result = await container_service.perform_action(network_id, NetworkAction.RESTART)

    return NetworkActionResponse(
        success=result["success"],
        message=result["message"],
        network_id=network_id,
        action=NetworkAction.RESTART,
        affected_containers=result["affected_containers"],
    )


@router.get("/{network_id}/config")
async def get_network_config(network_id: str):
    """
    Get configuration for a specific network.
    """
    if network_id not in settings.networks:
        raise HTTPException(status_code=404, detail=f"Network '{network_id}' not found")

    return settings.networks[network_id]


@router.put("/{network_id}/config")
async def update_network_config(network_id: str, update: NetworkConfigUpdate):
    """
    Update configuration for a specific network.
    Note: Some changes may require container restart to take effect.
    """
    if network_id not in settings.networks:
        raise HTTPException(status_code=404, detail=f"Network '{network_id}' not found")

    # For now, return the update - actual config changes would require
    # modifying torrc, i2pd.conf, etc. and restarting containers
    return {
        "success": True,
        "message": "Configuration update queued",
        "changes": update.model_dump(exclude_unset=True),
    }
