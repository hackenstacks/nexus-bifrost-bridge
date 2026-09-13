"""
NeXuS Command Center - Health Checker Service
Monitors health of all anonymity networks
"""

import asyncio
import logging
import socket
import time
from typing import Dict, Optional, Any
from datetime import datetime

import httpx
import aiohttp

from config import settings
from models import NetworkHealth, NetworkStatus
from services.podman import container_service

logger = logging.getLogger(__name__)


class HealthChecker:
    """Service for checking health of all networks"""

    def __init__(self):
        self.last_results: Dict[str, NetworkHealth] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background health checking"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._health_loop())
        logger.info("Health checker started")

    async def stop(self):
        """Stop background health checking"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health checker stopped")

    async def _health_loop(self):
        """Main health checking loop"""
        while self._running:
            try:
                await self.check_all()
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

            await asyncio.sleep(settings.health_check_interval)

    async def check_all(self) -> Dict[str, NetworkHealth]:
        """Check health of all networks"""
        tasks = []
        for network_id in settings.networks.keys():
            tasks.append(self.check_network(network_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, network_id in enumerate(settings.networks.keys()):
            if isinstance(results[i], Exception):
                self.last_results[network_id] = NetworkHealth(
                    network_id=network_id,
                    status=NetworkStatus.UNKNOWN,
                    last_check=datetime.utcnow(),
                    error=str(results[i])
                )
            else:
                self.last_results[network_id] = results[i]

        return self.last_results

    async def check_network(self, network_id: str) -> NetworkHealth:
        """Check health of a specific network"""
        network_config = settings.networks.get(network_id)
        if not network_config:
            return NetworkHealth(
                network_id=network_id,
                status=NetworkStatus.UNKNOWN,
                last_check=datetime.utcnow(),
                error="Network not configured"
            )

        # Check containers first
        containers = await container_service.get_network_containers(network_id)
        containers_up = sum(1 for c in containers if c.running)
        containers_total = len(network_config.get("containers", []))

        # If no containers configured (like 'direct'), skip container check
        if containers_total == 0:
            containers_up = 1
            containers_total = 1

        # Perform network-specific health check
        health_config = network_config.get("health_check", {})
        check_type = health_config.get("type", "none")

        latency = None
        details = {}
        error = None
        status = NetworkStatus.UNKNOWN

        try:
            if check_type == "socks":
                latency, details = await self._check_socks(health_config)
            elif check_type == "http":
                latency, details = await self._check_http(health_config)
            elif check_type == "admin":
                latency, details = await self._check_admin_socket(health_config)
            elif check_type == "rnstatus":
                latency, details = await self._check_reticulum(health_config)
            elif check_type == "interface":
                latency, details = await self._check_interface(health_config)
            elif check_type == "none":
                latency = 0
                details = {"message": "No health check configured"}

            # Determine status based on containers and health check
            if containers_up == 0 and containers_total > 0:
                status = NetworkStatus.DOWN
            elif containers_up < containers_total:
                status = NetworkStatus.DEGRADED
            elif latency is not None:
                status = NetworkStatus.UP
            else:
                status = NetworkStatus.DOWN

        except Exception as e:
            error = str(e)
            status = NetworkStatus.DOWN if containers_up == 0 else NetworkStatus.DEGRADED
            logger.debug(f"Health check for {network_id} failed: {e}")

        return NetworkHealth(
            network_id=network_id,
            status=status,
            latency_ms=latency,
            last_check=datetime.utcnow(),
            containers_up=containers_up,
            containers_total=containers_total,
            details=details,
            error=error
        )

    async def _check_socks(self, config: dict) -> tuple[Optional[float], dict]:
        """Check SOCKS proxy health by making a test request"""
        host = config.get("host", "127.0.0.1")
        port = config.get("port", 9050)
        test_url = config.get("test_url", "https://check.torproject.org/api/ip")

        start = time.time()

        try:
            # Use aiohttp with SOCKS proxy
            connector = aiohttp.TCPConnector(limit=1)
            async with aiohttp.ClientSession(connector=connector) as session:
                proxy = f"socks5://{host}:{port}"
                async with session.get(test_url, proxy=proxy, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    latency = (time.time() - start) * 1000
                    if response.status == 200:
                        data = await response.json()
                        return latency, {
                            "ip": data.get("IP"),
                            "is_tor": data.get("IsTor", False)
                        }
        except Exception as e:
            # Fallback: just check if port is open
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=5.0
                )
                latency = (time.time() - start) * 1000
                writer.close()
                await writer.wait_closed()
                return latency, {"connection": "ok", "tor_check": "failed"}
            except Exception:
                pass

        raise Exception(f"SOCKS proxy at {host}:{port} not responding")

    async def _check_http(self, config: dict) -> tuple[Optional[float], dict]:
        """Check HTTP service health"""
        host = config.get("host", "127.0.0.1")
        port = config.get("port", 80)
        path = config.get("path", "/")

        url = f"http://{host}:{port}{path}"
        start = time.time()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            latency = (time.time() - start) * 1000

            return latency, {
                "status_code": response.status_code,
                "content_length": len(response.content)
            }

    async def _check_admin_socket(self, config: dict) -> tuple[Optional[float], dict]:
        """Check admin socket (e.g., Yggdrasil)"""
        socket_path = config.get("socket", "/var/run/yggdrasil.sock")

        start = time.time()

        try:
            # For now, just check if socket exists
            import os
            if os.path.exists(socket_path):
                latency = (time.time() - start) * 1000
                return latency, {"socket": "exists"}
        except Exception:
            pass

        # Fallback: check if yggdrasil is reachable on IPv6
        return 0, {"status": "assumed_ok", "note": "Socket check not implemented in container"}

    async def _check_reticulum(self, config: dict) -> tuple[Optional[float], dict]:
        """Check Reticulum network status"""
        # Reticulum uses rnstatus command
        start = time.time()

        # For container deployment, we assume OK if container is running
        latency = (time.time() - start) * 1000
        return latency, {"status": "container_running"}

    async def _check_interface(self, config: dict) -> tuple[Optional[float], dict]:
        """Check network interface (e.g., bat0 for BATMAN-adv)"""
        interface = config.get("interface", "bat0")

        start = time.time()

        try:
            import os
            if os.path.exists(f"/sys/class/net/{interface}"):
                latency = (time.time() - start) * 1000
                return latency, {"interface": interface, "status": "up"}
        except Exception:
            pass

        return None, {"interface": interface, "status": "not_found"}

    def get_health(self, network_id: str) -> Optional[NetworkHealth]:
        """Get cached health for a network"""
        return self.last_results.get(network_id)

    def get_all_health(self) -> Dict[str, NetworkHealth]:
        """Get all cached health results"""
        return self.last_results.copy()


# Global health checker instance
health_checker = HealthChecker()
