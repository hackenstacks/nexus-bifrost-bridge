"""
NeXuS Screen Recorder Router — delegates to nexus-screenrec.sh
Exposes: /api/screenrec/{shot,rec,stop,status,files}
"""

import os
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/screenrec", tags=["screenrec"])

NEXUS_HOME = os.environ.get("NEXUS_HOME", os.path.expanduser("~/NeXuS"))
SCRIPT     = os.environ.get("NEXUS_SCREENREC", f"{NEXUS_HOME}/scripts/nexus-screenrec.sh")
VAULT      = os.environ.get("NEXUS_VAULT", f"{NEXUS_HOME}/vault")
SHOT_DIR   = Path(os.environ.get("NEXUS_SHOT_DIR", f"{VAULT}/screenshots"))
REC_DIR    = Path(os.environ.get("NEXUS_SCREENREC_DIR", f"{VAULT}/recordings"))


def _run(*args, timeout=15):
    if not os.path.exists(SCRIPT):
        raise HTTPException(503, f"nexus-screenrec.sh not found at {SCRIPT}")
    try:
        p = subprocess.run([SCRIPT, *args], capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0"),
                                "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", "wayland-0"),
                                "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")})
        return {"ok": p.returncode == 0, "out": p.stdout.strip(), "err": p.stderr.strip()}
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "nexus-screenrec.sh timed out")


@router.post("/shot")
async def shot():
    """Take a fullscreen screenshot."""
    return _run("shot")


@router.post("/shot-region")
async def shot_region():
    """Take a region screenshot (requires slurp GUI interaction)."""
    return _run("shot-region")


@router.post("/rec/start")
async def rec_start():
    """Start screen recording."""
    return _run("rec")


@router.post("/rec/stop")
async def rec_stop():
    """Stop screen recording."""
    return _run("stop")


@router.post("/audio/{state}")
async def audio(state: str):
    """Toggle audio capture: on or off."""
    if state not in ("on", "off"):
        raise HTTPException(400, "state must be 'on' or 'off'")
    return _run("audio", state)


@router.get("/status")
async def status():
    """Return recent files and recording state."""
    shots = sorted(SHOT_DIR.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)[:12]
    recs  = sorted(REC_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)[:6]
    pidfile = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "nexus-screenrec.pid"
    recording = pidfile.exists()
    return {
        "recording": recording,
        "screenshots": [{"name": f.name, "size": f.stat().st_size, "mtime": f.stat().st_mtime} for f in shots],
        "recordings":  [{"name": f.name, "size": f.stat().st_size, "mtime": f.stat().st_mtime} for f in recs],
    }


@router.get("/file/shot/{name}")
async def get_shot(name: str):
    """Serve a screenshot file."""
    p = SHOT_DIR / name
    if not p.exists() or not p.resolve().is_relative_to(SHOT_DIR.resolve()):
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png")


@router.get("/file/rec/{name}")
async def get_rec(name: str):
    """Serve a recording file."""
    p = REC_DIR / name
    if not p.exists() or not p.resolve().is_relative_to(REC_DIR.resolve()):
        raise HTTPException(404)
    return FileResponse(p, media_type="video/mp4")
