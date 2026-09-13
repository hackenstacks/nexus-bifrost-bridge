"""
NeXuS Command Center - Traffic Monitor Service
Real-time traffic monitoring and statistics
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional, Set, Callable, Any
from datetime import datetime
from collections import deque

import httpx

from config import settings
from models import (
    TrafficEvent,
    TrafficStats,
    NetworkTrafficStats,
    TrafficDirection,
    HAProxyStats,
)

logger = logging.getLogger(__name__)


class TrafficMonitor:
    """Service for monitoring network traffic"""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._subscribers: Set[Callable] = set()

        # Traffic event buffer (circular)
        self._events: deque = deque(maxlen=1000)

        # Current statistics
        self._stats = TrafficStats(
            timestamp=datetime.utcnow(),
            per_network={}
        )

        # HAProxy stats cache
        self._haproxy_stats: List[HAProxyStats] = []

        # Start time for uptime calculation
        self._start_time = time.time()

    async def start(self):
        """Start traffic monitoring"""
        if self._running:
            return

        self._running = True
        self._start_time = time.time()
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Traffic monitor started")

    async def stop(self):
        """Stop traffic monitoring"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Traffic monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                await self._poll_haproxy_stats()
                await self._update_stats()
                await self._notify_subscribers()
            except Exception as e:
                logger.error(f"Traffic monitor error: {e}")

            await asyncio.sleep(settings.traffic_poll_interval)

    async def _poll_haproxy_stats(self):
        """Poll HAProxy stats endpoint"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{settings.haproxy_stats_url};csv"
                )

                if response.status_code == 200:
                    self._haproxy_stats = self._parse_haproxy_csv(response.text)

        except Exception as e:
            logger.debug(f"Failed to poll HAProxy stats: {e}")

    def _parse_haproxy_csv(self, csv_text: str) -> List[HAProxyStats]:
        """Parse HAProxy CSV stats"""
        stats = []
        lines = csv_text.strip().split('\n')

        if len(lines) < 2:
            return stats

        # First line is header
        headers = lines[0].lstrip('# ').split(',')

        for line in lines[1:]:
            if not line or line.startswith('#'):
                continue

            values = line.split(',')
            if len(values) < len(headers):
                continue

            row = dict(zip(headers, values))

            try:
                stats.append(HAProxyStats(
                    backend=row.get('pxname', ''),
                    server=row.get('svname', ''),
                    status=row.get('status', 'UNKNOWN'),
                    weight=int(row.get('weight', 0) or 0),
                    active=row.get('status', '').upper() == 'UP',
                    current_sessions=int(row.get('scur', 0) or 0),
                    total_sessions=int(row.get('stot', 0) or 0),
                    bytes_in=int(row.get('bin', 0) or 0),
                    bytes_out=int(row.get('bout', 0) or 0),
                    response_time_ms=float(row.get('rtime', 0) or 0) if row.get('rtime') else None,
                    health_check_status=row.get('check_status', ''),
                ))
            except (ValueError, KeyError) as e:
                logger.debug(f"Failed to parse HAProxy row: {e}")

        return stats

    async def _update_stats(self):
        """Update traffic statistics from HAProxy data"""
        now = datetime.utcnow()

        # Aggregate by network
        network_stats: Dict[str, NetworkTrafficStats] = {}

        for stat in self._haproxy_stats:
            # Map backend to network
            network_id = self._backend_to_network(stat.backend)
            if not network_id:
                continue

            if network_id not in network_stats:
                network_config = settings.networks.get(network_id, {})
                network_stats[network_id] = NetworkTrafficStats(
                    network_id=network_id,
                    network_name=network_config.get('name', network_id),
                    network_icon=network_config.get('icon', '🌐'),
                )

            # Accumulate stats
            network_stats[network_id].bytes_in += stat.bytes_in
            network_stats[network_id].bytes_out += stat.bytes_out
            network_stats[network_id].connections += stat.current_sessions

        # Calculate totals
        total_in = sum(s.bytes_in for s in network_stats.values())
        total_out = sum(s.bytes_out for s in network_stats.values())
        total_conn = sum(s.connections for s in network_stats.values())

        self._stats = TrafficStats(
            timestamp=now,
            total_bytes_in=total_in,
            total_bytes_out=total_out,
            total_connections=total_conn,
            per_network=network_stats,
            uptime_seconds=int(time.time() - self._start_time),
        )

    def _backend_to_network(self, backend: str) -> Optional[str]:
        """Map HAProxy backend name to network ID"""
        backend = backend.lower()

        if 'tor' in backend:
            return 'tor'
        elif 'i2p' in backend:
            return 'i2p'
        elif 'ygg' in backend:
            return 'yggdrasil'
        elif 'reticulum' in backend or 'rns' in backend:
            return 'reticulum'
        elif 'batman' in backend or 'bat0' in backend:
            return 'batman'
        elif 'direct' in backend or 'bypass' in backend:
            return 'direct'
        elif 'privoxy' in backend:
            return 'tor'  # Privoxy forwards to Tor by default

        return None

    # ============================================
    # TRAFFIC EVENTS
    # ============================================

    def add_event(self, event: TrafficEvent):
        """Add a traffic event"""
        self._events.append(event)

    def get_events(self, limit: int = 100, networks: Optional[List[str]] = None) -> List[TrafficEvent]:
        """Get recent traffic events"""
        events = list(self._events)

        if networks:
            events = [e for e in events if e.network in networks]

        return events[-limit:]

    # ============================================
    # STATISTICS
    # ============================================

    def get_stats(self) -> TrafficStats:
        """Get current traffic statistics"""
        return self._stats

    def get_haproxy_stats(self) -> List[HAProxyStats]:
        """Get HAProxy backend statistics"""
        return self._haproxy_stats

    # ============================================
    # SUBSCRIBERS (for WebSocket)
    # ============================================

    def subscribe(self, callback: Callable):
        """Subscribe to traffic updates"""
        self._subscribers.add(callback)

    def unsubscribe(self, callback: Callable):
        """Unsubscribe from traffic updates"""
        self._subscribers.discard(callback)

    async def _notify_subscribers(self):
        """Notify all subscribers of updates"""
        if not self._subscribers:
            return

        data = {
            "type": "traffic_update",
            "stats": self._stats.model_dump(),
        }

        for callback in list(self._subscribers):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.debug(f"Subscriber notification failed: {e}")
                self._subscribers.discard(callback)


# Global traffic monitor instance
traffic_monitor = TrafficMonitor()
