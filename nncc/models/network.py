"""
NeXuS Command Center - Network Data Models
Pydantic models for network status and configuration
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class NetworkStatus(str, Enum):
    """Network operational status"""
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"
    STARTING = "starting"
    STOPPING = "stopping"


class ContainerStatus(BaseModel):
    """Individual container status"""
    name: str
    status: str
    running: bool
    health: Optional[str] = None
    uptime: Optional[str] = None
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None


class NetworkHealth(BaseModel):
    """Network health check result"""
    network_id: str
    status: NetworkStatus
    latency_ms: Optional[float] = None
    last_check: datetime
    containers_up: int = 0
    containers_total: int = 0
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class Network(BaseModel):
    """Complete network information"""
    id: str
    name: str
    icon: str
    color: str
    status: NetworkStatus = NetworkStatus.UNKNOWN
    health: Optional[NetworkHealth] = None
    containers: List[ContainerStatus] = []
    latency_ms: Optional[float] = None
    traffic_bytes_in: int = 0
    traffic_bytes_out: int = 0
    connections: int = 0
    config: Optional[Dict[str, Any]] = None


class NetworkAction(str, Enum):
    """Available network actions"""
    START = "start"
    STOP = "stop"
    RESTART = "restart"


class NetworkActionRequest(BaseModel):
    """Request to perform network action"""
    action: NetworkAction
    force: bool = False


class NetworkActionResponse(BaseModel):
    """Response from network action"""
    success: bool
    message: str
    network_id: str
    action: NetworkAction
    affected_containers: List[str] = []


class NetworkConfigUpdate(BaseModel):
    """Request to update network configuration"""
    tor_instances: Optional[int] = Field(None, ge=1, le=12)
    circuit_rotation_minutes: Optional[int] = Field(None, ge=1, le=60)
    exit_country: Optional[str] = None
    default_network: Optional[str] = None
    auto_failover: Optional[bool] = None
    failover_order: Optional[List[str]] = None
