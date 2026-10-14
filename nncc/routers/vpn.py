"""
NeXuS Command Center - VPN API Router
ProtonVPN (WireGuard / OpenVPN) + darknet control, delegated to nexus-vpn.sh.

One tool does one thing: the NCM owns no VPN logic — it calls the sovereign
nexus-vpn.sh CLI. Path is env-overridable ($NEXUS_VPN), no hardcoding.

NOTE: up/down/status/killswitch invoke `doas`. For web-triggered control the NCM
host needs a passwordless doas rule, e.g. in /etc/doas.d/nexus-vpn.conf:
    permit nopass <user> cmd <path>/nexus-vpn.sh
Read-only `configs` works without it; `ip` needs only network access.
"""

import os
import re
import subprocess
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/vpn", tags=["vpn"])

VPN = os.environ.get("NEXUS_VPN", os.path.expanduser("~/NeXuS/scripts/nexus-vpn.sh"))
_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _run(*args, timeout=30):
    if not os.path.exists(VPN):
        raise HTTPException(status_code=503, detail=f"nexus-vpn.sh not found at {VPN}")
    try:
        p = subprocess.run([VPN, *args], capture_output=True, text=True, timeout=timeout)
        return {
            "ok": p.returncode == 0,
            "code": p.returncode,
            "out": p.stdout.strip(),
            "err": p.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="nexus-vpn.sh timed out")


@router.get("/configs")
async def vpn_configs():
    """List available WireGuard/OpenVPN configs (read-only, no doas)."""
    r = _run("list")
    servers = []
    for line in r["out"].splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            servers.append({"proto": parts[0], "name": parts[1].strip()})
    return {"count": len(servers), "servers": servers}


@router.get("/status")
async def vpn_status():
    """Connection status + public IP/geo (🟢/🟡/🔴)."""
    return _run("status")


@router.get("/ip")
async def vpn_ip():
    """Current public IP + geo/org (reveals ProtonVPN when tunneled)."""
    return _run("ip")


@router.post("/up/{name}")
async def vpn_up(name: str):
    """Connect to a server by (fuzzy) name."""
    if not _NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid server name")
    return _run("up", name, timeout=45)


@router.post("/down")
async def vpn_down():
    """Disconnect."""
    return _run("down")


@router.post("/killswitch/{state}")
async def vpn_killswitch(state: str):
    """Killswitch on|off — traffic ceases if the VPN drops."""
    if state not in ("on", "off"):
        raise HTTPException(status_code=400, detail="state must be on|off")
    return _run("killswitch", state)


@router.post("/darknet/{state}")
async def vpn_darknet(state: str):
    """Darknet (Tor-over-VPN) on|off — SOCKS 127.0.0.1:9050."""
    if state not in ("on", "off"):
        raise HTTPException(status_code=400, detail="state must be on|off")
    return _run("darknet", state)
