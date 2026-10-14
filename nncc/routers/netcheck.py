"""NeXuS Command Center - Netcheck router. Delegates to nexus-netcheck.sh (one engine)."""
import json, os, subprocess
from fastapi import APIRouter

router = APIRouter(prefix="/netcheck", tags=["netcheck"])
NET = os.environ.get("NEXUS_NETCHECK",
                     os.path.expanduser("~/NeXuS/projects/nexus-netcheck/nexus-netcheck.sh"))


def _json(*args, timeout=40):
    try:
        p = subprocess.run([NET, *args], capture_output=True, text=True, timeout=timeout)
        out = p.stdout.strip()
        return json.loads(out) if out.startswith("{") else {"error": p.stderr.strip() or "no output"}
    except Exception as e:
        return {"error": str(e)}


@router.get("")
async def netcheck():
    """Live network stats: ip/geo, path, loss/latency/jitter, active conns, interfaces."""
    return _json("json")


@router.get("/speed")
async def netcheck_speed():
    """Download/upload speed test (Mbps)."""
    return _json("speed-json", timeout=70)
