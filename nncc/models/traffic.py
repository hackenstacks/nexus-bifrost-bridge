"""
NeXuS Command Center - Traffic Data Models
Pydantic models for traffic monitoring and statistics
"""

from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class TrafficDirection(str, Enum):
    """Traffic direction"""
    INBOUND = "in"
    OUTBOUND = "out"


class TrafficEvent(BaseModel):
    """Single traffic event"""
    timestamp: datetime
    source: str
    destination: str
    network: str
    network_icon: str
    bytes_transferred: int = 0
    direction: TrafficDirection = TrafficDirection.OUTBOUND
    protocol: str = "tcp"
    port: Optional[int] = None
    is_bypass: bool = False


class NetworkTrafficStats(BaseModel):
    """Traffic statistics for a single network"""
    network_id: str
    network_name: str
    network_icon: str
    bytes_in: int = 0
    bytes_out: int = 0
    connections: int = 0
    requests_per_second: float = 0.0


class TrafficStats(BaseModel):
    """Aggregate traffic statistics"""
    timestamp: datetime
    total_bytes_in: int = 0
    total_bytes_out: int = 0
    total_connections: int = 0
    per_network: Dict[str, NetworkTrafficStats] = {}
    uptime_seconds: int = 0


class TrafficHistoryEntry(BaseModel):
    """Historical traffic data point"""
    timestamp: datetime
    bytes_in: int
    bytes_out: int
    connections: int


class TrafficHistory(BaseModel):
    """Traffic history for charting"""
    network_id: str
    resolution: str = "1m"  # 1m, 5m, 1h, 1d
    data: List[TrafficHistoryEntry] = []


class LiveTrafficRequest(BaseModel):
    """Request for live traffic stream"""
    networks: Optional[List[str]] = None
    limit: int = 100
    include_bypass: bool = True


class HAProxyStats(BaseModel):
    """HAProxy statistics from stats socket"""
    backend: str
    server: str
    status: str
    weight: int
    active: bool
    current_sessions: int
    total_sessions: int
    bytes_in: int
    bytes_out: int
    response_time_ms: Optional[float] = None
    health_check_status: str
    last_change: Optional[datetime] = None
