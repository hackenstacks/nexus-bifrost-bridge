"""
NeXuS Command Center - API Routers
"""

from .networks import router as networks_router
from .routing import router as routing_router
from .traffic import router as traffic_router
from .health import router as health_router
from .vpn import router as vpn_router
from .netcheck import router as netcheck_router
from .heimdall import router as heimdall_router
from .screenrec import router as screenrec_router

__all__ = [
    "networks_router",
    "routing_router",
    "traffic_router",
    "health_router",
    "vpn_router",
    "netcheck_router",
    "heimdall_router",
    "screenrec_router",
]
