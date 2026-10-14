"""
NeXuS Command Center - Podman CLI Service
Container management via podman CLI (faster, more reliable than API)
"""

import asyncio
import logging
import subprocess
import json
import fnmatch
from typing import List, Dict, Optional, Any
from datetime import datetime

from config import settings
from models import ContainerStatus, NetworkAction

logger = logging.getLogger(__name__)


class PodmanCLIService:
    """Service for managing containers via podman CLI"""

    def __init__(self):
        self.runtime = "podman-cli"
        logger.info("Using Podman CLI for container management")

    async def _run_command(self, cmd: List[str], timeout: int = 2) -> tuple[bool, str, str]:
        """Run podman command and return (success, stdout, stderr)"""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            success = proc.returncode == 0
            return success, stdout.decode(), stderr.decode()
        except asyncio.TimeoutError:
            logger.error(f"Command timeout: {' '.join(cmd)}")
            return False, "", "Command timed out"
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return False, "", str(e)

    async def get_container_status(self, container_name: str) -> Optional[ContainerStatus]:
        """Get status of a single container"""
        success, stdout, stderr = await self._run_command([
            "podman", "inspect", "--format", "json", container_name
        ])

        if not success:
            return ContainerStatus(
                name=container_name,
                status="not_found",
                running=False,
            )

        try:
            data = json.loads(stdout)[0]
            state = data.get("State", {})
            return ContainerStatus(
                name=container_name,
                status=state.get("Status", "unknown"),
                running=state.get("Running", False),
                health=state.get("Health", {}).get("Status"),
                uptime=self._calculate_uptime(state.get("StartedAt")),
            )
        except Exception as e:
            logger.debug(f"Failed to parse status for {container_name}: {e}")
            return None

    async def get_all_containers(self, filter_prefix: str = "nexus-") -> List[ContainerStatus]:
        """Get status of all NeXuS containers"""
        success, stdout, stderr = await self._run_command([
            "podman", "ps", "-a", "--filter", f"name={filter_prefix}", "--format", "{{.Names}}:{{.Status}}"
        ], timeout=10)

        if not success:
            logger.error(f"Failed to list containers: {stderr}")
            return []

        containers = []
        for line in stdout.strip().split('\n'):
            if not line or ':' not in line:
                continue
            name, status = line.split(':', 1)
            if name.startswith(filter_prefix):
                running = status.lower().startswith('up')
                containers.append(ContainerStatus(
                    name=name,
                    status="running" if running else "stopped",
                    running=running,
                ))

        return containers

    async def get_network_containers(self, network_id: str) -> List[ContainerStatus]:
        """Get containers for a specific network (supports patterns like 'nexus-tor-*')"""
        network_config = settings.networks.get(network_id)
        if not network_config:
            return []

        containers = []
        patterns = network_config.get("containers", [])

        for pattern in patterns:
            if '*' in pattern:
                # For wildcard patterns, expand to known instances
                # Example: nexus-tor-* -> nexus-tor-01 through 06 + manager
                base = pattern.replace('*', '')

                # Try numbered instances (01-06 for Tor circuits)
                for i in range(1, 7):
                    name = f"{base}{i:02d}"
                    status = await self.get_container_status(name)
                    if status and status.status != "not_found":
                        containers.append(status)

                # Try common suffixes
                for suffix in ['manager', 'head1', 'head2', 'monitor']:
                    name = f"{base}{suffix}"
                    status = await self.get_container_status(name)
                    if status and status.status != "not_found":
                        containers.append(status)
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
        network_config = settings.networks.get(network_id)
        if not network_config:
            return {
                "success": False,
                "message": f"Unknown network: {network_id}",
                "affected_containers": []
            }

        # Get all containers for this network (handles patterns)
        containers = await self.get_network_containers(network_id)
        if not containers:
            return {
                "success": False,
                "message": f"No containers found for network: {network_id}",
                "affected_containers": []
            }

        affected = []
        errors = []

        for container in containers:
            cmd = ["podman", action.value, container.name]
            success, stdout, stderr = await self._run_command(cmd)

            if success:
                affected.append(container.name)
                logger.info(f"Action {action.value} on {container.name} successful")
            else:
                errors.append(f"{container.name}: {stderr}")
                logger.error(f"Action {action.value} on {container.name} failed: {stderr}")

        success = len(errors) == 0
        message = f"Action {action.value} completed on {len(affected)} containers"
        if errors:
            message += f" with {len(errors)} errors"

        return {
            "success": success,
            "message": message,
            "affected_containers": affected
        }

    def _calculate_uptime(self, started_at: Optional[str]) -> Optional[str]:
        """Calculate uptime from start time"""
        if not started_at:
            return None

        try:
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
container_service = PodmanCLIService()
