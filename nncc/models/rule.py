"""
NeXuS Command Center - Routing Rule Models
Pydantic models for bypass and routing rules
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class RuleType(str, Enum):
    """Types of routing rules"""
    DOMAIN = "domain"
    CIDR = "cidr"
    WILDCARD = "wildcard"
    REGEX = "regex"


class BypassRule(BaseModel):
    """Bypass rule configuration"""
    id: int
    pattern: str
    type: RuleType = RuleType.DOMAIN
    enabled: bool = True
    reason: Optional[str] = None


class BypassRuleCreate(BaseModel):
    """Request to create new bypass rule"""
    pattern: str = Field(..., min_length=1, max_length=255)
    type: RuleType = RuleType.DOMAIN
    enabled: bool = True
    reason: Optional[str] = Field(None, max_length=500)


class BypassRuleUpdate(BaseModel):
    """Request to update existing bypass rule"""
    pattern: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[RuleType] = None
    enabled: Optional[bool] = None
    reason: Optional[str] = Field(None, max_length=500)


class RoutingRule(BaseModel):
    """Network routing rule (domain -> network mapping)"""
    pattern: str
    network: str
    type: RuleType = RuleType.WILDCARD
    priority: int = 50
    enabled: bool = True
    description: Optional[str] = None


class RoutingConfig(BaseModel):
    """Complete routing configuration"""
    version: int = 1
    default_network: str = "tor"
    failover_order: List[str] = ["tor", "i2p", "yggdrasil", "reticulum", "batman", "direct"]
    auto_failover: bool = True
    routing_rules: List[RoutingRule] = []
    bypass_rules: List[BypassRule] = []


class DefaultRoutingUpdate(BaseModel):
    """Request to update default routing"""
    network: str
    failover_order: Optional[List[str]] = None
    auto_failover: Optional[bool] = None


class RuleMatchResult(BaseModel):
    """Result of matching a destination against rules"""
    destination: str
    matched_rule: Optional[str] = None
    network: str
    is_bypass: bool = False
    reason: Optional[str] = None
