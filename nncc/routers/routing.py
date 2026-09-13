"""
NeXuS Command Center - Routing API Router
Endpoints for bypass and routing rule management
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional

from models import (
    BypassRule,
    BypassRuleCreate,
    BypassRuleUpdate,
    RoutingRule,
    RoutingConfig,
    DefaultRoutingUpdate,
    RuleMatchResult,
)
from services import rules_manager, haproxy_config

router = APIRouter(prefix="/routing", tags=["routing"])


@router.get("/rules", response_model=RoutingConfig)
async def get_routing_config():
    """
    Get the complete routing configuration including all rules.
    """
    return rules_manager.get_config()


@router.get("/bypass", response_model=List[BypassRule])
async def list_bypass_rules():
    """
    List all bypass rules.

    Bypass rules allow specific domains, IPs, or patterns to
    connect directly without going through anonymity networks.
    """
    return rules_manager.get_bypass_rules()


@router.get("/bypass/{rule_id}", response_model=BypassRule)
async def get_bypass_rule(rule_id: int):
    """
    Get a specific bypass rule by ID.
    """
    rule = rules_manager.get_bypass_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Bypass rule {rule_id} not found")
    return rule


@router.post("/bypass", response_model=BypassRule, status_code=201)
async def create_bypass_rule(rule: BypassRuleCreate):
    """
    Create a new bypass rule.

    Bypass rules allow traffic to specified destinations to go
    directly without passing through Tor or other networks.

    Rule types:
    - domain: Exact domain match (e.g., "github.com")
    - wildcard: Wildcard pattern (e.g., "*.debian.org")
    - cidr: IP range (e.g., "192.168.0.0/16")
    - regex: Regular expression pattern
    """
    new_rule = await rules_manager.add_bypass_rule(rule)

    # Optionally regenerate HAProxy config
    # await haproxy_config.write_config()
    # await haproxy_config.reload_haproxy()

    return new_rule


@router.put("/bypass/{rule_id}", response_model=BypassRule)
async def update_bypass_rule(rule_id: int, update: BypassRuleUpdate):
    """
    Update an existing bypass rule.
    """
    updated = await rules_manager.update_bypass_rule(rule_id, update)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Bypass rule {rule_id} not found")

    return updated


@router.delete("/bypass/{rule_id}")
async def delete_bypass_rule(rule_id: int):
    """
    Delete a bypass rule.
    """
    deleted = await rules_manager.delete_bypass_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Bypass rule {rule_id} not found")

    return {"success": True, "message": f"Bypass rule {rule_id} deleted"}


@router.patch("/bypass/{rule_id}/toggle")
async def toggle_bypass_rule(rule_id: int):
    """
    Toggle a bypass rule enabled/disabled.
    """
    rule = rules_manager.get_bypass_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Bypass rule {rule_id} not found")

    update = BypassRuleUpdate(enabled=not rule.enabled)
    updated = await rules_manager.update_bypass_rule(rule_id, update)

    return {
        "success": True,
        "rule_id": rule_id,
        "enabled": updated.enabled,
    }


@router.get("/network-rules", response_model=List[RoutingRule])
async def list_network_rules():
    """
    List network routing rules (domain -> network mappings).

    These rules determine which network handles specific domain patterns:
    - *.onion -> Tor
    - *.i2p -> I2P
    - 200::/7 -> Yggdrasil
    """
    return rules_manager.get_routing_rules()


@router.get("/default")
async def get_default_routing():
    """
    Get default routing configuration.
    """
    config = rules_manager.get_config()
    return {
        "default_network": config.default_network,
        "failover_order": config.failover_order,
        "auto_failover": config.auto_failover,
    }


@router.put("/default")
async def update_default_routing(update: DefaultRoutingUpdate):
    """
    Update default routing configuration.

    Set which network handles traffic that doesn't match any rule,
    and configure failover behavior when networks go down.
    """
    config = await rules_manager.update_default_routing(
        network=update.network,
        failover_order=update.failover_order,
        auto_failover=update.auto_failover,
    )

    return {
        "success": True,
        "default_network": config.default_network,
        "failover_order": config.failover_order,
        "auto_failover": config.auto_failover,
    }


@router.get("/match")
async def match_destination(destination: str) -> RuleMatchResult:
    """
    Test which network would handle a specific destination.

    Useful for debugging routing rules without making actual requests.
    """
    return rules_manager.match_destination(destination)


@router.post("/apply")
async def apply_routing_changes():
    """
    Apply current routing rules to HAProxy configuration.

    This regenerates the HAProxy config file and signals HAProxy
    to reload without dropping connections.
    """
    config_written = await haproxy_config.write_config()
    if not config_written:
        raise HTTPException(status_code=500, detail="Failed to write HAProxy config")

    reloaded = await haproxy_config.reload_haproxy()

    return {
        "success": True,
        "config_written": config_written,
        "haproxy_reloaded": reloaded,
        "message": "Routing changes applied" if reloaded else "Config written, manual reload required",
    }
