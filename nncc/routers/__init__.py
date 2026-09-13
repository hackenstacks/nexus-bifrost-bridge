"""
NeXuS Command Center - API Routers
"""

from .networks import router as networks_router
from .routing import router as routing_router
from .traffic import router as traffic_router
from .health import router as health_router

__all__ = [
    "networks_router",
    "routing_router",
    "traffic_router",
    "health_router",
]
