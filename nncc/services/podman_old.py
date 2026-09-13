"""
NeXuS Command Center - Podman/Docker Service
Container management via Podman or Docker API
"""

import asyncio
import logging
import fnmatch
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path

try:
    from podman import PodmanClient
    PODMAN_AVAILABLE = True
except ImportError:
    PODMAN_AVAILABLE = False

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

from config import settings, CONTAINER_TO_NETWORK
from models import ContainerStatus, NetworkAction

logger = logging.getLogger(__name__)


class ContainerService:
    """Service for managing containers via Podman or Docker"""

    def __init__(self):
        self.client = None
        self.runtime = None
        self._connect()

    def _connect(self):
        """Connect to container runtime"""
        socket_path = settings.socket_path

        if settings.container_runtime == "podman" and PODMAN_AVAILABLE:
            try:
                if Path(socket_path).exists():
                    self.client = PodmanClient(base_url=f"unix://{socket_path}")
                    self.runtime = "podman"
                    logger.info(f"Connected to Podman via {socket_path}")
                    return
            except Exception as e:
                logger.warning(f"Failed to connect to Podman: {e}")

        if DOCKER_AVAILABLE:
            try:
                self.client = docker.from_env()
                self.runtime = "docker"
                logger.info("Connected to Docker")
                return
            except Exception as e:
                logger.warning(f"Failed to connect to Docker: {e}")

        logger.error("No container runtime available")
        self.runtime = None

    async def get_container_status(self, container_name: str) -> Optional[ContainerStatus]:
        """Get status of a single container"""
        if not self.client:
            return None

        try:
            if self.runtime == "podman":
                container = self.client.containers.get(container_name)
                attrs = container.attrs
                running = attrs.get("State", {}).get("Running", False)
                status = attrs.get("State", {}).get("Status", "unknown")

                return ContainerStatus(
                    name=container_name,
                    status=status,
                    running=running,
                    health=attrs.get("State", {}).get("Health", {}).get("Status"),
                    uptime=self._calculate_uptime(attrs.get("State", {}).get("StartedAt")),
                )
            else:  # docker
                container = self.client.containers.get(container_name)
                attrs = container.attrs
                running = attrs.get("State", {}).get("Running", False)
                status = attrs.get("State", {}).get("Status", "unknown")

                return ContainerStatus(
                    name=container_name,
                    status=status,
                    running=running,
                    health=attrs.get("State", {}).get("Health", {}).get("Status"),
                    uptime=self._calculate_uptime(attrs.get("State", {}).get("StartedAt")),
                )
        except Exception as e:
            logger.debug(f"Container {container_name} not found: {e}")
            return ContainerStatus(
                name=container_name,
                status="not_found",
                running=False,
            )

    async def get_all_containers(self, filter_prefix: str = "nexus-") -> List[ContainerStatus]:
        """Get status of all NeXuS containers"""
        if not self.client:
            return []

        containers = []
        try:
            all_containers = self.client.containers.list(all=True)
            for container in all_containers:
                name = container.name if hasattr(container, 'name') else container.attrs.get('Name', '').lstrip('/')
                if name.startswith(filter_prefix):
                    status = await self.get_container_status(name)
                    if status:
                        containers.append(status)
        except Exception as e:
            logger.error(f"Failed to list containers: {e}")

        return containers

    async def get_network_containers(self, network_id: str) -> List[ContainerStatus]:
        """Get containers for a specific network (supports patterns like 'nexus-tor-*')"""
        network_config = settings.networks.get(network_id)
        if not network_config:
            return []

        containers = []
        patterns = network_config.get("containers", [])

        # Get all nexus containers first
        all_containers = await self.get_all_containers()

        for pattern in patterns:
            if '*' in pattern:
                # Pattern matching for multi-instance
                for cont in all_containers:
                    if fnmatch.fnmatch(cont.name, pattern):
                        containers.append(cont)
            else:
                # Exact match
                status = await self.get_container_status(pattern)
                if status and status.status != "not_found":
                    containers.append(status)

        return containers

    async def perform_action(
        self,
        network_id: str,
        action: NetworkAction
    ) -> Dict[str, Any]:
        """Perform action on all containers in a network"""
        if not self.client:
            return {
                "success": False,
                "message": "No container runtime available",
                "affected_containers": []
            }

        network_config = settings.networks.get(network_id)
        if not network_config:
            return {
                "success": False,
                "message": f"Unknown network: {network_id}",
                "affected_containers": []
            }

        container_names = network_config.get("containers", [])
        if not container_names:
            return {
                "success": False,
                "message": f"No containers configured for network: {network_id}",
                "affected_containers": []
            }

        affected = []
        errors = []

        for container_name in container_names:
            try:
                container = self.client.containers.get(container_name)

                if action == NetworkAction.START:
                    container.start()
                elif action == NetworkAction.STOP:
                    container.stop()
                elif action == NetworkAction.RESTART:
                    container.restart()

                affected.append(container_name)
                logger.info(f"Action {action.value} on {container_name} successful")

            except Exception as e:
                errors.append(f"{container_name}: {str(e)}")
                logger.error(f"Action {action.value} on {container_name} failed: {e}")

        success = len(errors) == 0
        message = f"Action {action.value} completed on {len(affected)} containers"
        if errors:
            message += f" with {len(errors)} errors: {'; '.join(errors)}"

        return {
            "success": success,
            "message": message,
            "affected_containers": affected
        }

    async def get_container_stats(self, container_name: str) -> Optional[Dict[str, Any]]:
        """Get resource usage stats for a container"""
        if not self.client:
            return None

        try:
            container = self.client.containers.get(container_name)
            stats = container.stats(stream=False)

            # Calculate CPU percentage
            cpu_delta = stats.get('cpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0) - \
                       stats.get('precpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0)
            system_delta = stats.get('cpu_stats', {}).get('system_cpu_usage', 0) - \
                          stats.get('precpu_stats', {}).get('system_cpu_usage', 0)

            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * 100.0

            # Memory usage
            memory = stats.get('memory_stats', {})
            memory_usage = memory.get('usage', 0) / (1024 * 1024)  # MB

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_mb": round(memory_usage, 2),
                "network_rx": stats.get('networks', {}).get('eth0', {}).get('rx_bytes', 0),
                "network_tx": stats.get('networks', {}).get('eth0', {}).get('tx_bytes', 0),
            }
        except Exception as e:
            logger.debug(f"Failed to get stats for {container_name}: {e}")
            return None

    def _calculate_uptime(self, started_at: Optional[str]) -> Optional[str]:
        """Calculate uptime from start time"""
        if not started_at:
            return None

        try:
            # Parse ISO format timestamp
            if started_at.endswith('Z'):
                started_at = started_at[:-1] + '+00:00'
            start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            now = datetime.now(start_time.tzinfo)
            delta = now - start_time

            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            if days > 0:
                return f"{days}d {hours}h"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except Exception:
            return None


# Global service instance
container_service = ContainerService()
