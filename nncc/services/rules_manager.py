"""
NeXuS Command Center - Rules Manager Service
Manages bypass and routing rules with persistence
"""

import json
import logging
import asyncio
import re
import ipaddress
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from watchfiles import awatch

from config import settings
from models import (
    BypassRule,
    BypassRuleCreate,
    BypassRuleUpdate,
    RoutingRule,
    RoutingConfig,
    RuleType,
    RuleMatchResult,
)

logger = logging.getLogger(__name__)


class RulesManager:
    """Service for managing routing and bypass rules"""

    def __init__(self):
        self.rules_path = settings.data_dir / settings.rules_file
        self._config: Optional[RoutingConfig] = None
        self._lock = asyncio.Lock()
        self._watch_task: Optional[asyncio.Task] = None

    async def load(self) -> RoutingConfig:
        """Load rules from disk"""
        async with self._lock:
            if not self.rules_path.exists():
                # Create default config
                self._config = RoutingConfig()
                await self._save_locked()
                return self._config

            try:
                with open(self.rules_path, 'r') as f:
                    data = json.load(f)

                # Parse into config
                bypass_rules = [
                    BypassRule(**r) for r in data.get("bypass_rules", [])
                ]
                routing_rules = [
                    RoutingRule(**r) for r in data.get("routing_rules", [])
                ]

                self._config = RoutingConfig(
                    version=data.get("version", 1),
                    default_network=data.get("default_network", "tor"),
                    failover_order=data.get("failover_order", ["tor", "i2p", "yggdrasil"]),
                    auto_failover=data.get("auto_failover", True),
                    routing_rules=routing_rules,
                    bypass_rules=bypass_rules,
                )

                # Store next_bypass_id for new rules
                self._next_bypass_id = data.get("next_bypass_id",
                    max([r.id for r in bypass_rules], default=0) + 1
                )

                logger.info(f"Loaded {len(bypass_rules)} bypass rules and {len(routing_rules)} routing rules")
                return self._config

            except Exception as e:
                logger.error(f"Failed to load rules: {e}")
                self._config = RoutingConfig()
                return self._config

    async def save(self):
        """Save rules to disk"""
        async with self._lock:
            await self._save_locked()

    async def _save_locked(self):
        """Save while holding lock"""
        if not self._config:
            return

        # Ensure directory exists
        self.rules_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self._config.version,
            "default_network": self._config.default_network,
            "failover_order": self._config.failover_order,
            "auto_failover": self._config.auto_failover,
            "routing_rules": [r.model_dump() for r in self._config.routing_rules],
            "bypass_rules": [r.model_dump() for r in self._config.bypass_rules],
            "next_bypass_id": getattr(self, '_next_bypass_id',
                max([r.id for r in self._config.bypass_rules], default=0) + 1
            ),
            "last_modified": datetime.utcnow().isoformat(),
        }

        with open(self.rules_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.debug("Rules saved to disk")

    def get_config(self) -> RoutingConfig:
        """Get current routing configuration"""
        if not self._config:
            raise RuntimeError("Rules not loaded")
        return self._config

    # ============================================
    # BYPASS RULES
    # ============================================

    def get_bypass_rules(self) -> List[BypassRule]:
        """Get all bypass rules"""
        if not self._config:
            return []
        return self._config.bypass_rules

    def get_bypass_rule(self, rule_id: int) -> Optional[BypassRule]:
        """Get a specific bypass rule"""
        for rule in self.get_bypass_rules():
            if rule.id == rule_id:
                return rule
        return None

    async def add_bypass_rule(self, rule: BypassRuleCreate) -> BypassRule:
        """Add a new bypass rule"""
        async with self._lock:
            new_id = getattr(self, '_next_bypass_id', 1)
            self._next_bypass_id = new_id + 1

            new_rule = BypassRule(
                id=new_id,
                pattern=rule.pattern,
                type=rule.type,
                enabled=rule.enabled,
                reason=rule.reason,
            )

            self._config.bypass_rules.append(new_rule)
            await self._save_locked()

            logger.info(f"Added bypass rule {new_id}: {rule.pattern}")
            return new_rule

    async def update_bypass_rule(self, rule_id: int, update: BypassRuleUpdate) -> Optional[BypassRule]:
        """Update an existing bypass rule"""
        async with self._lock:
            for i, rule in enumerate(self._config.bypass_rules):
                if rule.id == rule_id:
                    # Apply updates
                    update_data = update.model_dump(exclude_unset=True)
                    updated_rule = rule.model_copy(update=update_data)
                    self._config.bypass_rules[i] = updated_rule

                    await self._save_locked()
                    logger.info(f"Updated bypass rule {rule_id}")
                    return updated_rule

            return None

    async def delete_bypass_rule(self, rule_id: int) -> bool:
        """Delete a bypass rule"""
        async with self._lock:
            original_len = len(self._config.bypass_rules)
            self._config.bypass_rules = [
                r for r in self._config.bypass_rules if r.id != rule_id
            ]

            if len(self._config.bypass_rules) < original_len:
                await self._save_locked()
                logger.info(f"Deleted bypass rule {rule_id}")
                return True

            return False

    # ============================================
    # ROUTING RULES
    # ============================================

    def get_routing_rules(self) -> List[RoutingRule]:
        """Get all routing rules"""
        if not self._config:
            return []
        return self._config.routing_rules

    # ============================================
    # DEFAULT ROUTING
    # ============================================

    async def update_default_routing(
        self,
        network: Optional[str] = None,
        failover_order: Optional[List[str]] = None,
        auto_failover: Optional[bool] = None
    ) -> RoutingConfig:
        """Update default routing configuration"""
        async with self._lock:
            if network is not None:
                self._config.default_network = network
            if failover_order is not None:
                self._config.failover_order = failover_order
            if auto_failover is not None:
                self._config.auto_failover = auto_failover

            await self._save_locked()
            return self._config

    # ============================================
    # RULE MATCHING
    # ============================================

    def match_destination(self, destination: str) -> RuleMatchResult:
        """Match a destination against all rules"""
        # First check bypass rules
        for rule in self.get_bypass_rules():
            if not rule.enabled:
                continue

            if self._matches_pattern(destination, rule.pattern, rule.type):
                return RuleMatchResult(
                    destination=destination,
                    matched_rule=rule.pattern,
                    network="direct",
                    is_bypass=True,
                    reason=rule.reason,
                )

        # Then check routing rules
        matched_routing = None
        for rule in sorted(self.get_routing_rules(), key=lambda r: -r.priority):
            if not rule.enabled:
                continue

            if self._matches_pattern(destination, rule.pattern, rule.type):
                matched_routing = rule
                break

        if matched_routing:
            return RuleMatchResult(
                destination=destination,
                matched_rule=matched_routing.pattern,
                network=matched_routing.network,
                is_bypass=False,
                reason=matched_routing.description,
            )

        # Default routing
        return RuleMatchResult(
            destination=destination,
            matched_rule=None,
            network=self._config.default_network,
            is_bypass=False,
            reason="Default routing",
        )

    def _matches_pattern(self, destination: str, pattern: str, rule_type: RuleType) -> bool:
        """Check if destination matches a pattern"""
        destination = destination.lower()
        pattern = pattern.lower()

        if rule_type == RuleType.DOMAIN:
            # Exact domain match or subdomain match
            return destination == pattern or destination.endswith('.' + pattern)

        elif rule_type == RuleType.WILDCARD:
            # Convert wildcard to regex
            regex = pattern.replace('.', r'\.').replace('*', '.*')
            return bool(re.match(f'^{regex}$', destination))

        elif rule_type == RuleType.CIDR:
            # CIDR matching for IP addresses
            try:
                network = ipaddress.ip_network(pattern, strict=False)
                addr = ipaddress.ip_address(destination)
                return addr in network
            except ValueError:
                return False

        elif rule_type == RuleType.REGEX:
            try:
                return bool(re.match(pattern, destination))
            except re.error:
                return False

        return False

    # ============================================
    # FILE WATCHING
    # ============================================

    async def start_watching(self):
        """Start watching rules file for changes"""
        if self._watch_task:
            return

        self._watch_task = asyncio.create_task(self._watch_loop())
        logger.info("Started watching rules file")

    async def stop_watching(self):
        """Stop watching rules file"""
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None

    async def _watch_loop(self):
        """Watch for file changes and reload"""
        try:
            async for changes in awatch(self.rules_path.parent):
                for change_type, path in changes:
                    if Path(path).name == settings.rules_file:
                        logger.info("Rules file changed, reloading")
                        await self.load()
        except asyncio.CancelledError:
            pass


# Global rules manager instance
rules_manager = RulesManager()
