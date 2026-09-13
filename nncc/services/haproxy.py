"""
NeXuS Command Center - HAProxy Configuration Generator
Generates dynamic HAProxy configuration from routing rules
"""

import logging
from typing import List, Optional
from pathlib import Path

from config import settings
from models import BypassRule, RoutingRule, RuleType
from services.rules_manager import rules_manager

logger = logging.getLogger(__name__)


class HAProxyConfigGenerator:
    """Service for generating HAProxy configuration"""

    def __init__(self):
        self.config_path = Path(settings.haproxy_config_path)

    def generate_config(self) -> str:
        """Generate complete HAProxy configuration"""
        config = rules_manager.get_config()

        sections = [
            self._generate_global(),
            self._generate_defaults(),
            self._generate_stats_frontend(),
            self._generate_unified_frontend(config.bypass_rules, config.routing_rules),
            self._generate_backends(),
        ]

        return '\n'.join(sections)

    def _generate_global(self) -> str:
        """Generate global section"""
        return """# NeXuS Command Center - Smart HAProxy Configuration
# Auto-generated - Manual edits will be overwritten

global
    daemon
    user haproxy
    group haproxy
    log stdout local0 info
    stats timeout 30s

    # Stats socket for runtime API
    stats socket /var/run/haproxy/admin.sock mode 660 level admin expose-fd listeners

    # Security
    ssl-default-bind-ciphers ECDHE+AESGCM:ECDHE+CHACHA20:RSA+AESGCM:RSA+AES:!aNULL:!MD5:!DSS
    ssl-default-bind-options ssl-min-ver TLSv1.2 no-tls-tickets
"""

    def _generate_defaults(self) -> str:
        """Generate defaults section"""
        return """
defaults
    timeout connect 10s
    timeout client 60s
    timeout server 60s
    timeout check 10s
    retries 3
    option redispatch
    option dontlognull
    log global
"""

    def _generate_stats_frontend(self) -> str:
        """Generate stats frontend"""
        return """
# ============================================
# STATISTICS INTERFACE
# ============================================
frontend stats
    bind *:8404
    mode http
    stats enable
    stats uri /stats
    stats refresh 5s
    stats admin if TRUE
    stats realm "NeXuS Command Center Statistics"

    # Health check endpoint
    monitor-uri /health
"""

    def _generate_unified_frontend(
        self,
        bypass_rules: List[BypassRule],
        routing_rules: List[RoutingRule]
    ) -> str:
        """Generate unified proxy frontend with ACL routing"""
        acls = []
        use_backends = []

        # Generate ACLs for bypass rules
        for rule in bypass_rules:
            if not rule.enabled:
                continue

            acl_name = f"bypass_{rule.id}"

            if rule.type == RuleType.DOMAIN:
                acls.append(f"    acl {acl_name} hdr(host) -i {rule.pattern}")
                acls.append(f"    acl {acl_name} hdr(host) -i -m end .{rule.pattern}")
            elif rule.type == RuleType.WILDCARD:
                pattern = rule.pattern.replace('*', '')
                acls.append(f"    acl {acl_name} hdr(host) -i -m end {pattern}")
            elif rule.type == RuleType.CIDR:
                acls.append(f"    acl {acl_name} src {rule.pattern}")

            use_backends.append(f"    use_backend direct_backend if {acl_name}")

        # Generate ACLs for routing rules (network-specific domains)
        for rule in routing_rules:
            if not rule.enabled:
                continue

            acl_name = f"route_{rule.network}_{hash(rule.pattern) & 0xFFFF:04x}"

            if rule.pattern.endswith('.onion'):
                acls.append(f"    acl {acl_name} hdr(host) -i -m end .onion")
            elif rule.pattern.endswith('.i2p'):
                acls.append(f"    acl {acl_name} hdr(host) -i -m end .i2p")
            elif rule.pattern.endswith('.b32.i2p'):
                acls.append(f"    acl {acl_name} hdr(host) -i -m end .b32.i2p")
            elif '200::' in rule.pattern or rule.pattern.startswith('200:'):
                # Yggdrasil IPv6
                acls.append(f"    acl {acl_name} dst 200::/7")
            else:
                continue  # Skip non-domain patterns for HTTP proxy

            use_backends.append(f"    use_backend {rule.network}_backend if {acl_name}")

        acl_section = '\n'.join(acls) if acls else "    # No custom ACLs defined"
        use_section = '\n'.join(use_backends) if use_backends else ""

        return f"""
# ============================================
# UNIFIED SOCKS5 PROXY - Main Entry Point
# Port 9050: SOCKS5 with automatic network routing
# ============================================
frontend unified_socks_proxy
    bind *:9050
    mode tcp
    option tcplog

    # Default to Tor pool
    default_backend tor_socks_pool

# ============================================
# HTTP PROXY - Smart Routing (Port 8118 via Privoxy)
# ============================================
frontend http_proxy_lb
    bind *:8881
    mode http
    option httplog

    # Routing ACLs
{acl_section}

    # I2P routing (.i2p domains)
    acl is_i2p hdr(host) -i -m end .i2p
    acl is_i2p_b32 hdr(host) -i -m end .b32.i2p

    # Tor routing (.onion domains)
    acl is_onion hdr(host) -i -m end .onion

{use_section}

    # Route I2P domains to I2P backend
    use_backend i2p_http_backend if is_i2p
    use_backend i2p_http_backend if is_i2p_b32

    # Route .onion to Tor
    use_backend tor_http_backend if is_onion

    # Default: Privoxy -> Tor
    default_backend privoxy_backend

# ============================================
# ADDITIONAL SOCKS5 PORTS
# ============================================
frontend socks_proxy_lb
    bind *:8884
    bind *:8885
    bind *:8886
    mode tcp
    option tcplog
    default_backend tor_socks_pool

# ============================================
# HIGH BANDWIDTH PORT (Least Connections)
# ============================================
frontend high_bandwidth_proxy
    bind *:8887
    mode tcp
    default_backend tor_high_bandwidth
"""

    def _generate_backends(self) -> str:
        """Generate all backend definitions"""
        return """
# ============================================
# TOR SOCKS5 POOL (Round-Robin)
# ============================================
backend tor_socks_pool
    mode tcp
    balance roundrobin
    option tcp-check

    server tor-01 nexus-tor-01:9050 check inter 30s rise 2 fall 3
    server tor-02 nexus-tor-02:9050 check inter 30s rise 2 fall 3
    server tor-03 nexus-tor-03:9050 check inter 30s rise 2 fall 3
    server tor-04 nexus-tor-04:9050 check inter 30s rise 2 fall 3
    server tor-05 nexus-tor-05:9050 check inter 30s rise 2 fall 3
    server tor-06 nexus-tor-06:9050 check inter 30s rise 2 fall 3

# ============================================
# TOR HIGH BANDWIDTH (Least Connections)
# ============================================
backend tor_high_bandwidth
    mode tcp
    balance leastconn
    option tcp-check

    server fast-01 nexus-tor-01:9050 check inter 10s weight 100
    server fast-02 nexus-tor-02:9050 check inter 10s weight 100
    server fast-03 nexus-tor-03:9050 check inter 10s weight 80
    server fast-04 nexus-tor-04:9050 check inter 10s weight 80
    server fast-05 nexus-tor-05:9050 check inter 10s weight 60
    server fast-06 nexus-tor-06:9050 check inter 10s weight 60

# ============================================
# TOR HTTP (via SOCKS)
# ============================================
backend tor_http_backend
    mode http
    balance roundrobin

    # Use Privoxy for HTTP-to-SOCKS conversion
    server privoxy nexus-proxy:8118 check inter 30s

# ============================================
# PRIVOXY BACKEND
# ============================================
backend privoxy_backend
    mode http
    balance roundrobin

    server privoxy-01 nexus-proxy:8118 check inter 30s

# ============================================
# I2P HTTP BACKEND
# ============================================
backend i2p_http_backend
    mode http
    balance roundrobin

    server i2p-http nexus-i2p:4444 check inter 60s

# ============================================
# DIRECT BACKEND (Bypass)
# ============================================
backend direct_backend
    mode http
    balance roundrobin

    # Direct connection (no proxy)
    # This requires httpchk with a real server
    # For true bypass, client should connect directly
    http-request set-header X-Nexus-Bypass "true"
    server direct 127.0.0.1:65535 disabled

    # Actually: redirect or forward to system default
    http-request redirect location https://%[hdr(host)]%[url] code 302
"""

    async def write_config(self) -> bool:
        """Generate and write HAProxy configuration"""
        try:
            config = self.generate_config()
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, 'w') as f:
                f.write(config)

            logger.info(f"HAProxy config written to {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to write HAProxy config: {e}")
            return False

    async def reload_haproxy(self) -> bool:
        """Signal HAProxy to reload configuration"""
        import asyncio
        import os

        try:
            # Try to send SIGHUP via stats socket
            socket_path = settings.haproxy_socket

            if os.path.exists(socket_path):
                reader, writer = await asyncio.open_unix_connection(socket_path)
                writer.write(b"reload\n")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                logger.info("HAProxy reload signaled via socket")
                return True

        except Exception as e:
            logger.warning(f"Socket reload failed, trying SIGHUP: {e}")

        # Fallback: try sending SIGHUP to haproxy process
        try:
            import subprocess
            result = subprocess.run(
                ["pkill", "-HUP", "haproxy"],
                capture_output=True
            )
            if result.returncode == 0:
                logger.info("HAProxy reload signaled via SIGHUP")
                return True

        except Exception as e:
            logger.error(f"Failed to reload HAProxy: {e}")

        return False


# Global config generator instance
haproxy_config = HAProxyConfigGenerator()
