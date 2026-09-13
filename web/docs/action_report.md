# nexus-web - Action Report

**Project:** /home/user/nexus-web
**Created:** 2026-08-07

---


## Server Status Dashboard + Hub Nav (2026-08-07 14:10)

**Status:** ✅ TESTED

**What:** Built live server health dashboard at /servers/ and added Servers nav button to project hub.

**Why:** No single place to see what services are running, their health, logs, and config paths. The 10-version-bug problem — need one canonical view of node state.

**How:**
- Added /api/servers endpoint to nexus_web_server.py — runs pgrep, port checks, log tails, /proc/PID/status for RAM. Returns JSON for 6 services: NeXuS Web Server, Conduit, Caddy, NXS Search, Fail2ban, Darkman
- Stripped ANSI codes + null bytes from log output (conduit log was dirty)
- Fixed conduit proc_info to match /usr/bin/conduit not supervise-daemon
- Created ~/nexus-web/servers/index.html — dark neon theme, expandable service cards, status dots (green/amber/red), badges (PID, RAM, port), log tail viewer, file/dir links with one-click copy, docs links, auto-refresh 30s
- Added ⬡ Servers button to hub header (~/nexus-web/index.html line 352)

**Files:**
- ~/Projects/nexus-web-server/nexus_web_server.py (added _servers_status method + route)
- ~/nexus-web/servers/index.html (new)
- ~/nexus-web/index.html (Servers button added)

**Testing:** curl -sk https://localhost:8443/api/servers confirmed all 6 services reporting. Page live at https://localhost:8443/servers/

**Dependencies:** nexus-api-proxy running (api-proxy start)

---

