# bifrost-bridge Action Report

---

## 2026-09-13 — Full Bifrost-Bridge Build + NNCC Wire-up

**Status:** ✅ TESTED — all services running

### What
Built and wired the NeXuS Bifrost-Bridge web gateway. Migrated scattered files to ~/NeXuS/bifrost-bridge/. Wired NNCC to Python FastAPI backend. Added theme engine. Registered in v2 catalog.

### Files Map

| URL | Backend | Key Files |
|-----|---------|-----------|
| https://localhost:8443/ | Static (nexus_web_server.py) | bifrost-bridge/server/nexus_web_server.py |
| https://localhost:8443/nncc/ | FastAPI :8801 | bifrost-bridge/nncc/index.html, js/app.js |
| https://localhost:8443/nncc/api/* | FastAPI :8801 | bifrost-bridge/nncc/main.py + routers/ |
| https://localhost:8443/grafana/ | Grafana :3000 | /etc/grafana.ini |
| https://localhost:8443/api/theme | nexus_web_server.py | web/static/hljs/.active-theme |
| https://localhost:8443/static/hljs/nexus-active-theme.css | nexus_web_server.py | web/static/hljs/styles/ |
| https://localhost:8443/static/hljs/theme-picker.html | Static | web/static/hljs/theme-picker.html |
| https://localhost:8443/api/llm/* | nexus_web_server.py | ~/NeXuS/secrets/nexus.env (keys) |

### Services

| Service | Port | Started by |
|---------|------|------------|
| nexus_web_server.py | :8443 | api-proxy → nexus-proxy tmux |
| NNCC FastAPI | :8801 | api-proxy → nexus-nncc tmux |
| Grafana | :3000 | OpenRC |
| Loki | :3100 | OpenRC |
| Prometheus | :9090 | OpenRC |
| Vector | — | OpenRC |

## Added VPN/darknet option to NCM (nncc) — /api/vpn/* (2026-09-28 20:40)

Status: ✅ WIRED (all files ast-parse clean; live test needs the nncc FastAPI venv running). What: VPN + darknet control as an option in the Bifrost-Bridge NeXuS Connection Manager. Why: user wanted the ProtonVPN/darknet toggle available in the bridge. How: new FastAPI router nncc/routers/vpn.py (prefix /vpn) that delegates to the sovereign nexus-vpn.sh CLI (path via $NEXUS_VPN env, no hardcode) — one tool does one thing. Endpoints under /api: GET /vpn/configs (list WG+OVPN), /vpn/status (🟢/🟡/🔴 + IP), /vpn/ip; POST /vpn/up/{name} (name validated ^[A-Za-z0-9._-]+$), /vpn/down, /vpn/killswitch/{on|off}, /vpn/darknet/{on|off}. Wired via routers/__init__.py (vpn_router export) + main.py (import + include_router prefix /api). subprocess with timeouts, returns {ok,code,out,err}; 503 if script missing, 504 on timeout. SECURITY: write actions call doas → needs passwordless rule /etc/doas.d/nexus-vpn.conf: 'permit nopass <user> cmd <path>/nexus-vpn.sh' (documented in router); read-only configs/ip work without. Files: nncc/routers/vpn.py (new); nncc/routers/__init__.py + nncc/main.py (backups .bak-20260928-203837). NEXT: frontend panel in nncc dashboard (buttons → these endpoints). Delegates to: nexus-vpn.sh (WG+OpenVPN+killswitch+darknet).

---


## NCM VPN frontend panel — dashboard tab wired to /api/vpn/* (2026-09-28 20:46)

Status: ✅ BUILT (index.html + app.js validate; node --check app.js clean; live browser test needs nncc FastAPI + bifrost proxy running). What: full frontend for the VPN/darknet option in the NCM dashboard. How: (1) index.html — added 🔐 VPN nav-tab + #tab-vpn panel (card w/ status-badge 🟢/🟡/🔴, public-IP line, WG+OpenVPN server <select>, Connect/Disconnect, Killswitch toggle, Darknet toggle, live <pre> output, doas note); (2) js/app.js — showTab hook loads VPN on tab open; loadVpn() populates servers from /vpn/configs + calls vpnStatus(); vpnStatus() parses status output for 🟢/🟡/🔴 + killswitch/darknet ON + 🌐 IP line, updates badge/toggles/IP; vpnUp/vpnDown/vpnKillswitch/vpnDarknet() POST to endpoints w/ showNotification toasts + delayed re-status. Chain: UI → /nncc/api/vpn/* (API_BASE=/nncc/api) → FastAPI vpn_router → nexus-vpn.sh. Also: nexus-vpn.sh status() now emits 🧅 darknet: ON so the frontend reads both toggles. Files: nncc/index.html + nncc/js/app.js (backups .bak-20260928-204317); nexus-vpn.sh (darknet status line). Full VPN stack complete: CLI (WG+OpenVPN+killswitch+darknet+TUI) + setup + cockpit + Bridge API + NCM dashboard panel. Run: start nncc FastAPI + bifrost proxy, open dashboard → VPN tab.

---


## OC + Bifrost streaming fixed — end-to-end working (2026-10-14 01:10)

**Status:** ✅ TESTED — OC sends message, gets streaming response

**What:** Fixed OpenCharacters (index.html) routing through Bifrost to Pollinations with full SSE streaming.

**Why:** Multiple compounding bugs blocked OC from working through the proxy.

**Bugs fixed (in order):**
1. OC inject script not applied to registry-served HTML — fixed _registry_static to also inject
2. Seeded endpointUrl had /v1 baked in — OC appends /v1/chat/completions, causing double /v1/v1/
3. Fetch interceptor routed api.openai.com → openai (no key) — changed to → pollinations
4. MAP values had /v1 causing double-v1 — removed /v1 from all MAP entries
5. Bifrost was HTTP/1.0 — fetch getReader() needs HTTP/1.1; set protocol_version=HTTP/1.1
6. HTTP/1.1 keep-alive hung static responses — added close_connection=True in _send
7. Raw 301 redirect in _dispatch_registry missing Content-Length:0 — fixed
8. Pollinations sends preamble SSE chunk with choices:[] — OC crashes on json.choices[0]; Bifrost now filters these out before forwarding

**Files:**
- ~/NeXuS/bifrost-bridge/server/nexus_web_server.py

**Testing:** OC at https://localhost:8443/oc/index.html — sent message, got streaming response ✅

---


## OC-Fix: Full Classification Report — All 8 Bugs (2026-10-14 01:13)

**Status:** ✅ TESTED — OC fully working through Bifrost → Pollinations with streaming

**Classification:** OC-Fix
**File:** ~/NeXuS/bifrost-bridge/server/nexus_web_server.py

---

## BUG 1 — OC-Fix-01: Inject script not applied to registry-served HTML

**Symptom:** OC loaded but API calls went directly to api.openai.com, no proxy.
**Root cause:** Two code paths serve HTML files. The `_serve_static()` path (direct /oc/* URLs) had `_OC_INJECT` applied. The `_registry_static()` path (when /oc is registered in the app registry as static+static) did NOT. OC was being served via the registry path.
**Fix:** Added inject block to `_registry_static()`:
  if app['prefix'] in ('/oc', '/oc/') and ctype == 'text/html':
      if 'NeXuS proxy auto-config' not in html_str:
          data = inject...
**Why it works:** Injection now fires regardless of which code path serves the HTML.

---

## BUG 2 — OC-Fix-02: Double /v1/v1/ in API URL (stale IndexedDB)

**Symptom:** Error 'unknown API route /api/llm/pollinations/v1/v1/chat/completions'
**Root cause:** The seeded IndexedDB customModelConfigs had endpointUrl as BASE+'/api/llm/pollinations/v1'. OC appends '/v1/chat/completions' to whatever endpointUrl is. Result: /api/llm/pollinations/v1 + /v1/chat/completions = double v1. The seedDB guard (if result exists, return early) also meant old stale values were never overwritten on subsequent loads.
**Fix 1:** Changed seeded endpointUrl to BASE+'/api/llm/pollinations' (no /v1) so OC appends /v1/chat/completions cleanly.
**Fix 2:** Removed the guard — seedDB now always overwrites customModelConfigs.
**Fix 3:** Added runtime double-v1 fixer in the fetch interceptor as belt-and-suspenders:
  url = url.replace(/(\/api\/llm\/[^\/]+)\/v1\/v1\//, '$1/v1/')
**Why it works:** No /v1 in seed + always-overwrite seed + runtime fixer = triple redundancy against stale DB.

---

## BUG 3 — OC-Fix-03: api.openai.com routed to openai provider (no key)

**Symptom:** handleStreamingResponse error — OC received an error JSON instead of an SSE stream.
**Root cause:** OC hardcodes 'https://api.openai.com/v1/chat/completions' for ALL streaming calls regardless of which model is selected in the UI. The fetch interceptor MAP had 'api.openai.com' → BASE+'/api/llm/openai/v1'. Bifrost has no OpenAI key (openai=false in health). Bifrost returned a JSON error. OC's handleStreamingResponse tried to read it as an SSE stream and crashed.
**Fix:** Changed MAP entry:
  Before: 'api.openai.com' → BASE+'/api/llm/openai/v1'
  After:  'api.openai.com' → BASE+'/api/llm/pollinations'
**Why it works:** All OC streaming calls now route to Pollinations which is keyless and always available.

---

## BUG 4 — OC-Fix-04: /v1 in MAP values causing double-v1

**Symptom:** Same double-v1 error but from the fetch interceptor path.
**Root cause:** MAP had '/v1' baked in (BASE+'/api/llm/groq/v1'). OC's call to https://api.openai.com/v1/chat/completions strips the host, keeps '/v1/chat/completions', appends to MAP value → double v1.
**Fix:** Removed /v1 from ALL MAP values:
  'api.openai.com' → BASE+'/api/llm/pollinations'  (no /v1)
  'api.mistral.ai' → BASE+'/api/llm/mistral'
  'api.groq.com'   → BASE+'/api/llm/groq'
  etc.
**Why it works:** OC provides the /v1/chat/completions path. Bifrost's LLM_PATH_RE already handles both /v1/ and bare /chat/completions with (?:v1/)? optional group.

---

## BUG 5 — OC-Fix-05: HTTP/1.0 broke fetch streaming (getReader)

**Symptom:** handleStreamingResponse crashed — response.body was null or unreadable.
**Root cause:** Bifrost's BaseHTTPRequestHandler defaulted to HTTP/1.0. The Fetch API's response.body.pipeThrough(TextDecoderStream()).getReader() requires HTTP/1.1 to expose a proper ReadableStream. HTTP/1.0 responses do not support streaming reads via the Fetch API in modern browsers.
**Fix:** Added to Handler class:
  protocol_version = 'HTTP/1.1'
**Why it works:** HTTP/1.1 exposes response.body as a ReadableStream. The browser can call reader.read() and receive chunks as they arrive.

---

## BUG 6 — OC-Fix-06: HTTP/1.1 keep-alive hung static responses / links broken

**Symptom:** After adding HTTP/1.1, all static routes hung. Browser links on Bifrost hub stopped working. curl returned 200 for first request then hung indefinitely.
**Root cause:** HTTP/1.1 uses persistent connections by default. After Bifrost sent a response, it kept the connection open waiting for another request. Responses without Content-Length or Transfer-Encoding caused the browser to wait forever for more data before rendering.
**Fix 1:** Added close_connection = True in _send() for all non-streaming responses:
  if 'Connection' not in extra and 'Transfer-Encoding' not in extra:
      self.close_connection = True
**Fix 2:** Added Content-Length: 0 and close_connection = True to raw 301 redirect in _dispatch_registry (bypassed _send).
**Why it works:** Non-streaming responses close after delivery. Streaming responses explicitly set Transfer-Encoding: chunked + Connection: keep-alive, exempting them from the close rule.

---

## BUG 7 — OC-Fix-07: /oc (no trailing slash) blocked in browser

**Symptom:** Navigating to https://localhost:8443/oc showed 'Blocked' in Firefox DevTools with 0 bytes transferred.
**Root cause:** The 301 redirect from /oc → /oc/ in _dispatch_registry used raw send_response(301) without going through _send(). It sent no Content-Length header and did not set close_connection. With HTTP/1.1, the browser waited for more data after the 301 headers and the response appeared to hang/block.
**Fix:** Added to the _dispatch_registry redirect:
  self.close_connection = True
  self.send_header('Content-Length', '0')
**Why it works:** Browser now knows the 301 response body is empty and closes, allowing it to follow the redirect immediately.

---

## BUG 8 — OC-Fix-08: Pollinations SSE preamble chunk with choices:[] crashed OC

**Symptom:** handleStreamingResponse error — TypeError at json.choices[0].text.
**Root cause:** Pollinations always sends a first SSE event as a content-filter results preamble: data: {'choices':[],'prompt_filter_results':[...]}. The choices array is empty. OC's handleStreamingResponse does json.choices[0].text without checking if choices[0] exists. This throws TypeError: Cannot read properties of undefined. OC has no try-catch around this specific line so the error propagates up and kills the entire reply.
**Fix:** Added SSE line filter in Bifrost's streaming proxy. While reading the upstream SSE stream, each complete line is inspected:
  - If it's a data: line (not [DONE])
  - And JSON parses successfully
  - And choices is an empty list
  → drop the line, do not forward to browser
**Why it works:** OC never sees the empty-choices preamble. First chunk it receives always has choices[0] populated with a role or content delta. No TypeError.

---

## What Now Works

- https://localhost:8443/oc/index.html loads cleanly
- No API key prompts (nexus-proxy seeded into IndexedDB)
- All OC streaming chat calls route → Bifrost → Pollinations
- SSE stream decoded properly, reply streams into OC chat window
- All other Bifrost routes (/, /search, /nncc, /docs, etc.) unaffected

## Architecture Summary

  Browser OC → fetch('https://api.openai.com/v1/chat/completions')
    ↓ _OC_INJECT fetch interceptor (rewrites URL, strips Auth header)
  fetch('https://localhost:8443/api/llm/pollinations/v1/chat/completions')
    ↓ Bifrost LLM proxy (is_stream=True path)
    ↓ Filter empty choices[] preamble chunks
    ↓ HTTP/1.1 Transfer-Encoding: chunked SSE stream
  OC handleStreamingResponse → reader.read() → text chunks → rendered reply

---

