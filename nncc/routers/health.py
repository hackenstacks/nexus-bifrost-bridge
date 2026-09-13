"""
NeXuS Command Center - Health API Router
Endpoints for system and network health monitoring
"""

from fastapi import APIRouter
from typing import Dict, Any
from datetime import datetime

from config import settings
from models import NetworkHealth, NetworkStatus
from services import health_checker, container_service, traffic_monitor

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def get_system_health():
    """
    Get overall system health status.

    Returns:
    - Overall system status
    - Per-network health details
    - Container summary
    - Traffic summary
    """
    # Get all network health
    network_health = health_checker.get_all_health()

    # Calculate overall status
    statuses = [h.status for h in network_health.values()]
    if all(s == NetworkStatus.UP for s in statuses):
        overall = "healthy"
    elif all(s == NetworkStatus.DOWN for s in statuses):
        overall = "down"
    elif any(s == NetworkStatus.DOWN for s in statuses):
        overall = "degraded"
    else:
        overall = "unknown"

    # Get container summary
    containers = await container_service.get_all_containers()
    running = sum(1 for c in containers if c.running)

    # Get traffic summary
    traffic = traffic_monitor.get_stats()

    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat(),
        "networks": {
            net_id: {
                "status": health.status.value,
                "latency_ms": health.latency_ms,
                "containers": f"{health.containers_up}/{health.containers_total}",
                "last_check": health.last_check.isoformat() if health.last_check else None,
                "error": health.error,
            }
            for net_id, health in network_health.items()
        },
        "containers": {
            "running": running,
            "total": len(containers),
        },
        "traffic": {
            "total_bytes": traffic.total_bytes_in + traffic.total_bytes_out,
            "connections": traffic.total_connections,
            "uptime_seconds": traffic.uptime_seconds,
        }
    }


@router.get("/networks")
async def get_all_network_health() -> Dict[str, NetworkHealth]:
    """
    Get health status of all networks.
    """
    return health_checker.get_all_health()


@router.get("/networks/{network_id}")
async def get_network_health(network_id: str):
    """
    Get health status of a specific network.
    """
    health = health_checker.get_health(network_id)
    if not health:
        return {
            "network_id": network_id,
            "status": "unknown",
            "message": "No health data available"
        }
    return health


@router.post("/check")
async def trigger_health_check():
    """
    Trigger an immediate health check of all networks.

    Normally health checks run on a schedule, but this endpoint
    allows forcing an immediate check.
    """
    results = await health_checker.check_all()

    return {
        "success": True,
        "checked_at": datetime.utcnow().isoformat(),
        "results": {
            net_id: {
                "status": health.status.value,
                "latency_ms": health.latency_ms,
            }
            for net_id, health in results.items()
        }
    }


@router.get("/containers")
async def get_container_health():
    """
    Get health status of all NeXuS containers.
    """
    containers = await container_service.get_all_containers()

    return {
        "containers": [
            {
                "name": c.name,
                "status": c.status,
                "running": c.running,
                "health": c.health,
                "uptime": c.uptime,
            }
            for c in containers
        ],
        "summary": {
            "total": len(containers),
            "running": sum(1 for c in containers if c.running),
            "stopped": sum(1 for c in containers if not c.running),
        }
    }


@router.get("/haproxy")
async def get_haproxy_health():
    """
    Get HAProxy load balancer health status.
    """
    haproxy_stats = traffic_monitor.get_haproxy_stats()

    backends = {}
    for stat in haproxy_stats:
        if stat.backend not in backends:
            backends[stat.backend] = {
                "servers": [],
                "active_count": 0,
                "total_count": 0,
            }

        backends[stat.backend]["servers"].append({
            "name": stat.server,
            "status": stat.status,
            "active": stat.active,
            "sessions": stat.current_sessions,
            "response_time_ms": stat.response_time_ms,
        })

        backends[stat.backend]["total_count"] += 1
        if stat.active:
            backends[stat.backend]["active_count"] += 1

    return {
        "backends": backends,
        "total_servers": len(haproxy_stats),
        "active_servers": sum(1 for s in haproxy_stats if s.active),
    }


@router.get("/ready")
async def readiness_check():
    """
    Kubernetes-style readiness probe.

    Returns 200 if the service is ready to accept traffic.
    """
    # Check if critical services are running
    health = health_checker.get_all_health()

    # At least Tor should be up for the system to be "ready"
    tor_health = health.get("tor")
    if tor_health and tor_health.status == NetworkStatus.UP:
        return {"ready": True}

    return {"ready": False, "reason": "Tor network not available"}


@router.get("/live")
async def liveness_check():
    """
    Kubernetes-style liveness probe.

    Returns 200 if the service is alive and not deadlocked.
    """
    return {"alive": True, "timestamp": datetime.utcnow().isoformat()}
